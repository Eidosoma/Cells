// The Machines view: a catalogue of the molecular machines of the species shown
// (schema/MACHINE_CATALOGUE.md). Asked for on 17 November 2026: a tab of its own, gathered by
// species as the proteins were, in a design of its own.
//
// The machines lie on a bench in trays, one tray for each thing they do. A machine with a
// published size is a simple shape at that size, every one at the same scale (one unit is ten
// nanometres), with a scale bar etched on the bench; a machine with no size in hand is a card
// with its name, the same for all, and the legend says a card is not to scale. Choosing a machine
// lifts it and lights it; a machine with a closer view (the flagellar motor) is drawn from its
// own file (machine_parts.js), as an outline among the others and with its parts when chosen,
// its subunits a step further, as its closer view in the Cell view draws it. Every level is an
// illustration, and the panel says what the record states Cells models of it, and nothing else.
//
// Every visual difference stands for one thing (MARKS, below); the bench, the trays' rims and
// the scale bar's line are the room. No colour, glow or height is a status.

import * as THREE from "../three.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { disposeTree } from "../core/stage.js";
import { fitView, plaqueMesh } from "./laws_marks.js";
import { buildMachine, describeMachinePart } from "./machine_parts.js";
import { loadBeside } from "./protein_shelves.js";
import { IONS, PREFIX, kindOf, byFamily, organelleKind } from "./machines_data.js";
import { catalogueOf, describe as describeItem, describePart, sections as listSections, levelsOf, shapeWords, speciesLabel, SHAPE_LEVEL, SWATCH, groupSwatch, NONE_FOUND, noneFoundNote } from "./machines_card.js";
import { h } from "../ui/dom.js";
import { loadShape, buildShape } from "./machine_shape.js";
import { layoutOf, bodiesAt, membraneOf, partOfChain, shelfOf, CARD, TRAY, BENCH, UNIT_NM, SHELF } from "./machines_layout.js";
import { organelleModels, simpleModel, placeModel, scaleFor, drawnSize, paintModel, MODELS as SHELF_MODELS, SIMPLE } from "./machines_shelf.js";

/** The look this view asks of the stage (core/look.js), as the Laws library's: natural colours under filmic light. */
export const MACHINES_LOOK = { rich: true, filmic: true, exposure: 1.04, contact: true, reach: 0.5, shade: 0.55 };
/** Each group's colour: a token of the page's palette (page.css), one for each thing the machines do. */
// Each group's own colour, told apart in both themes: the three groups the dossiers brought take colours no other tray has.
export const GROUP_HUE = { proteins: "bioRibosome", genes: "bioNucleus", dna: "bioGolgi", light: "bioChloroplast", atp: "bioFuel", ions: "bioIon", membranes: "bioEr", folding: "bioProtein", breaking: "bioSignal", moving: "bioMito", surface: "bioCell", tagging: "bioSignal", metabolism: "bioFuel", binding: "bioMembrane", redox: "bioWater", cleavage: "bioPump", traffic: "bioWound", unknown: "bioCyto" };
/** What each role of a machine file's part wears (as its closer view, machine_view.js, dresses it). */
const ROLE_HUE = { membrane: ["bioMembrane", 0.32, true], wall: ["ghost", 0.36, true], rotor: ["bioProtein", 1], stator: ["bioMito", 1], bearing: ["edge", 1], export: ["bioIon", 1], mark: ["fg", 1], swept: ["fg", 0.3, true], arrow: ["fg", 1] };
const VIEW = { azimuth: 0.12, polar: 0.98 };
const LIFT = 0.7; // how far a chosen machine rises from its tray
const MACHINE_SCALE = 1000 / UNIT_NM; // a machine file is drawn in micrometres; here one unit is ten nanometres
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
/** The bench as a stop of its own (a press on its mark at the shelf's stop travels down to it); its panel says what it is. */
export const BENCH_ID = "machines:bench";
/** Milliseconds of travel for each power of ten the scale changes by: every power of ten takes the same time. */
export const PER_POWER = 900;
/** The powers of ten the rail is marked in, in nanometres, from 10 µm down to 10 nm. */
export const POWERS = [10000, 1000, 100, 10];
/** How the nucleus's wedge (cut toward the Cell view's camera) is turned to face this view's camera, a little to one side, as there. */
const FACING = { nucleus: -0.4 };
/** A length in nanometres in the scale bar's words. */
export const lengthWords = (nm) => (nm >= 1000 ? `${Number((nm / 1000).toPrecision(3))} µm` : `${Number(nm.toPrecision(3))} nm`);
const columnsFor = (stage) => (stage.width && stage.height && stage.width < stage.height * 0.9 ? 1 : 3);

/** What each visual difference stands for: the legend's words. `when` says when a mark is drawn at all. */
export const MARKS = [
  { id: SWATCH.sized, label: "A shape: drawn to scale from a size in hand", description: "A simple shape at a size in hand, every one at the same scale (the scale bar on the bench is 100 nm): a size a paper or a species' file gives, or the viewer's own measure from a structure of the Protein Data Bank. Shapes, not structures.", when: (lens) => lens.counts.sized > 0 },
  { id: SWATCH.card, label: "A card: no size in hand, not to scale", description: "A machine whose size no source in hand gives: a card with its name, the same size for all. It is a label, not a shape.", when: (lens) => lens.counts.cards > 0 },
  { id: "mach-found", label: "Forward: found; faint: not found", description: "While a search is set, the machines it finds stand as they are and the rest fade.", when: (lens) => Boolean(lens.query) },
  { id: SWATCH.organelle, label: "On the shelf: organelles, at the same scale", description: "Behind the bench, the cell's organelles at the bench's one scale, the small ones on a plank of their own: each drawn with the Cell view's model of it where there is one, else with a simple model, an illustration, at a size its panel gives with its source (a measurement in one cell type, or a general figure); one with no size in hand is a card. The rail at the side travels between the bench and the shelf.", when: (lens) => (lens.organelles?.length || 0) > 0 },
  { id: SWATCH.chosen, label: "Blue light: your choice", description: "The machine you chose rises from its tray and is lit; a part or a chain you chose in it is lit the same blue.", when: () => true },
];
export const MACHINES_NOTE = "The bench, the trays and the scale bar's line are the room, and stand for nothing; a tray's colour is the group's.";

export class MachinesLens {
  constructor(stage, model, labels) {
    this.id = "machines";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.catalogue = catalogueOf(model.raw);
    this.species = null;
    this.root = new THREE.Group();
    this.selected = null;
    this.query = "";
    this.level = 2; // the level a chosen machine with a closer view is drawn at
    this.machines = new Map(); // a machine file's data, by its page id, once read
    this.measured = {};
    this.lifts = new Map();
    this.active = false;
    this.columns = columnsFor(stage);
    this.wantsLeftRoom = true; // the viewer leaves the bench clear of its cards on the left (stage.setInsets left), as for the Laws library
    this.materials = this.makeMaterials();
    this.counts = { machines: 0, sized: 0, cards: 0, laws: 0, groups: 0 };
    this.organelles = []; // the species' organelles, on the shelf behind the bench
    this.shelf = null; // the shelf as drawn: its layout, its models and their holders (made when first wanted)
    this.travel = null; // a travel between stops under way: { from, to, elapsed, duration }
    this.loupe = null; // a machine held beside an organelle: { machine, organelle }
    this.stop = "bench"; // the stop the view stands at: the bench, the shelf, or a power of ten
  }

  // ------------------------------------------------------------ materials

  makeMaterials() {
    const standard = (options) => new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.05, ...options });
    const materials = {
      bench: standard({ roughness: 0.66, metalness: 0.08 }),
      tray: standard({ roughness: 0.4, metalness: 0.2, envMapIntensity: 0.9 }),
      card: standard({ roughness: 0.42, metalness: 0.08 }),
      tab: standard({ roughness: 0.4 }),
      scale: new THREE.MeshBasicMaterial({ toneMapped: false }),
      lit: new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.5, metalness: 0, emissiveIntensity: 0.85, envMapIntensity: 0.4, toneMapped: false }),
      groups: new Map(),
    };
    materials.lit.userData.noContact = true;
    materials.scale.userData.noContact = true;
    return materials;
  }

  groupMaterial(group) {
    if (!this.materials.groups.has(group)) this.materials.groups.set(group, new THREE.MeshStandardMaterial({ roughness: 0.38, metalness: 0.06, envMapIntensity: 1 }));
    return this.materials.groups.get(group);
  }

  // ------------------------------------------------------------ the picture

  /** The species shown: its machines are laid out again, and a choice that is not among them is let go. */
  setSpecies(id) {
    if (!id || id === this.species) return;
    this.species = id;
    this.measured = {};
    this.stop = "bench";
    this.loupe = this.lastMachine = this.lastOrganelle = null;
    this.travel = null;
    if (this.selected && !this.has(this.selected)) this.selected = null;
    this.build();
    if (this.active) this.afterBuild(true);
    this.onChrome?.();
    this.readBench();
  }

  /**
   * The species' bench, read from beside the page when it is first shown (schema/MACHINE_CATALOGUE.md, `benches`): the
   * bench stands with its units meanwhile, and is built again when its machines are in; one that cannot be read leaves
   * the units standing, and the card says why. While it is read the view is not `ready`: the viewer waits on it before
   * it chooses what an address or a door names, so that a machine, a part or a unit is chosen on the bench laid out.
   */
  readBench() {
    const species = this.species;
    if (!this.catalogue || !species || this.catalogue.hasBench(species) || this.catalogue.benchState(species) || this.benchReading?.species === species) return;
    const promise = this.catalogue.loadBench(species).then(() => {
      if (this.benchReading?.promise === promise) this.benchReading = null;
      if (this.species !== species || this.disposed) return;
      // What was chosen while it was read (a unit pressed meanwhile, the List): chosen again on the bench as laid out
      // now, at its own levels; the camera that was sent to it goes to its place, else to the whole bench.
      const held = this.selected, aim = this.focused?.id;
      this.measured = {};
      this.selected = this.selectedPart = null;
      this.build();
      if (held && this.has(held)) this.setSelection(held);
      if (this.active) {
        this.afterBuild(false);
        // Where it now stands on the bench (a machine the species lacks stands nowhere: the whole bench, then).
        const there = aim && aim === this.selected && this.layout.items.some((item) => item.id === (this.partOf(aim) || this.measuredPart(aim)?.owner || aim));
        if (there) this.focus(aim);
        else this.stage.rig?.setView(this.homeView());
      }
      this.onChrome?.();
      this.onOpen?.();
      this.stage.invalidate?.();
    });
    this.benchReading = { species, promise };
  }

  /** Settles once the species' bench is read and laid out (the viewer waits on it); nothing while none is being read. */
  get ready() {
    return this.benchReading?.species === this.species ? this.benchReading.promise : null;
  }

  /** What the viewer waits on before it chooses `id`: the bench, while it is read and the id (a part, a chain) is not yet known. */
  waitsFor(id) {
    return this.ready && !this.has(id) ? this.ready : null;
  }

  /** Where the bench is laid out anew (a new width, a machine's own file read): the camera sent to the choice follows it. */
  reaim() {
    const aim = this.focused?.id;
    if (aim && this.active && (aim === this.selected || aim === this.selectedPart)) this.focus(aim);
  }

  item(id) {
    return this.catalogue && this.species ? this.catalogue.item(this.species, id) : null;
  }

  /** The machine a part's id belongs to (`machine:<kind>:<part>`, `unit.<id>:<part>`), while that machine is drawn with its parts. */
  partOf(id) {
    const kind = kindOf(id);
    const owner = kind ? `${PREFIX}${kind}` : /^unit\.[^:]+:/.test(id || "") ? id.split(":")[0] : null;
    if (!owner || id === owner) return null;
    const built = this.built?.get(owner);
    return built && built.level >= 2 && built.ids.has(id) ? owner : null;
  }

  /**
   * A part or chain of a measured machine of the species shown, named by its id before the machine is drawn with it
   * (an address, a link): its machine's id and the level that draws it. Null for any other id.
   */
  measuredPart(id) {
    if (typeof id !== "string") return null;
    const kind = kindOf(id);
    const owner = kind ? `${PREFIX}${kind}` : /^unit\.[^:]+:/.test(id) ? id.split(":")[0] : null;
    if (!owner || owner === id) return null;
    const size = this.item(owner)?.size, name = id.slice(owner.length + 1);
    if (size?.shape !== "measured") return null;
    if (size.parts?.some((part) => part.id === name)) return { owner, level: 2 };
    if (size.chains?.some((chain) => chain.id === name)) return { owner, level: 3 };
    return null;
  }

  build() {
    if (this.labels && this.active) this.labels.clear();
    for (const child of [...this.root.children]) {
      this.root.remove(child);
      if (child.userData.keep) continue;
      child.traverse((object) => {
        object.geometry?.dispose?.();
        if (object.material && object.material.map) object.material.map.dispose();
        if (object.material?.userData?.own) object.material.dispose();
      });
    }
    this.built = new Map();
    this.lifts.clear();
    const items = this.catalogue && this.species ? this.catalogue.of(this.species) : [];
    this.counts = this.catalogue && this.species ? this.catalogue.counts(this.species) : this.counts;
    this.layout = layoutOf(items, this.catalogue?.groups || [], { columns: this.columns, measured: this.measured, ions: IONS });
    this.layoutBench = Boolean(this.catalogue?.hasBench(this.species));
    const { trays, items: placed, bench, scale } = this.layout;
    // The bench and the trays: the room.
    const benchMesh = new THREE.Mesh(new THREE.BoxGeometry(bench.w, BENCH.h, bench.d), this.materials.bench);
    benchMesh.position.set(bench.x, -BENCH.h / 2, bench.z);
    benchMesh.userData.unpickable = true;
    this.root.add(benchMesh);
    // The trays: their floors and rims as two instanced meshes for the whole bench (the room costs two draws, however
    // many trays); the back rim of each wears its group's colour, as an instance colour.
    const boxes = [], backs = [];
    const t = 0.45;
    for (const tray of trays) {
      boxes.push({ x: tray.x, y: 0.15, z: tray.z, w: tray.w, h: 0.3, d: tray.d });
      boxes.push({ x: tray.x, y: TRAY.h / 2, z: tray.z + tray.d / 2 - t / 2, w: tray.w, h: TRAY.h, d: t });
      boxes.push({ x: tray.x - tray.w / 2 + t / 2, y: TRAY.h / 2, z: tray.z, w: t, h: TRAY.h, d: tray.d });
      boxes.push({ x: tray.x + tray.w / 2 - t / 2, y: TRAY.h / 2, z: tray.z, w: t, h: TRAY.h, d: tray.d });
      backs.push({ x: tray.x, y: TRAY.h / 2, z: tray.z - tray.d / 2 + t / 2, w: tray.w, h: TRAY.h, d: t, group: tray.group });
    }
    const instanced = (items, material) => {
      const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), material, Math.max(1, items.length));
      mesh.count = items.length;
      const dummy = new THREE.Object3D();
      items.forEach((item, index) => {
        dummy.position.set(item.x, item.y, item.z);
        dummy.scale.set(item.w, item.h, item.d);
        dummy.updateMatrix();
        mesh.setMatrixAt(index, dummy.matrix);
      });
      mesh.computeBoundingSphere();
      mesh.userData.unpickable = true;
      this.root.add(mesh);
      return mesh;
    };
    this.trayMeshes = [instanced(boxes, this.materials.tray), instanced(backs, this.materials.rim ??= new THREE.MeshStandardMaterial({ roughness: 0.38, metalness: 0.06, envMapIntensity: 1 }))];
    this.trayBacks = backs;
    this.trayMeshes[1].instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, backs.length) * 3).fill(1), 3);
    // The cards: one body and one coloured tab each, as instances; picked by their instance.
    const cards = placed.filter((entry) => entry.type === "card");
    this.cardList = cards;
    const body = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), this.materials.card, Math.max(1, cards.length));
    const tab = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), this.materials.tab, Math.max(1, cards.length));
    body.count = tab.count = cards.length;
    for (const mesh of [body, tab]) {
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, cards.length) * 3).fill(1), 3);
      mesh.userData.pick = (hit) => cards[hit.instanceId]?.id || null;
      this.root.add(mesh);
    }
    this.cardBody = body;
    this.cardTab = tab;
    this.placeCards();
    // The shapes: each its own mesh, at its size; a machine with a file is built from it once it is read.
    this.shapeMeshes = new Map();
    for (const entry of placed.filter((value) => value.type === "shape")) {
      const holder = new THREE.Group();
      holder.position.set(entry.x, entry.y, entry.z);
      holder.userData.pick = entry.id;
      const shape = entry.shape;
      if (shape.kind === "ellipsoid") {
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 40, 28), this.groupMaterial(entry.group));
        mesh.scale.set(shape.w, shape.h, shape.d);
        mesh.position.y = shape.h / 2;
        holder.add(mesh);
      } else if (shape.kind === "rod") {
        const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(shape.radius, Math.max(0.01, shape.length - 2 * shape.radius), 12, 32), this.groupMaterial(entry.group));
        mesh.rotation.z = Math.PI / 2;
        mesh.position.y = shape.radius;
        holder.add(mesh);
      } else if (shape.kind === "machine") {
        this.buildMachineAt(entry, holder);
      } else if (shape.kind === "measured") {
        this.buildMeasuredAt(entry, holder);
      }
      this.root.add(holder);
      this.shapeMeshes.set(entry.id, { entry, holder });
    }
    this.buildOutlines();
    // The names written on the cards, lying flat, and on each tray's head; the scale bar and its words.
    this.writeNames();
    if (scale) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(scale.length, 0.08, 0.4), this.materials.scale);
      bar.position.set(scale.x + scale.length / 2, 0.04, scale.z);
      bar.userData.unpickable = true;
      this.root.add(bar);
      this.scaleBar = bar;
    } else this.scaleBar = null;
    // The shelf of the species' organelles behind the bench (schema/MACHINE_CATALOGUE.md, "Organelles"): drawn when first
    // wanted (ensureShelf), and kept across a build of the bench where it stands where it stood (its clipping planes are set
    // where it stands, so a shelf that would move is made again).
    this.organelles = this.catalogue && this.species ? this.catalogue.organellesOf(this.species) : [];
    this.views = null;
    if (this.shelf && (this.shelf.species !== this.species || this.shelf.anchor !== this.layout.bounds.minZ || this.shelf.count !== this.organelles.length)) this.dropShelf();
    if (this.shelf) this.root.add(this.shelf.root);
    this.applyColours();
  }

  // ------------------------------------------------------------ the shelf, the stops and the travel between them

  /**
   * The shelf, made when first wanted: each organelle the Cell view's own model of it (machines_shelf.js, built by its
   * builders from the species' cell), or a simple model of its own where the Cell view has none, set at the size its species'
   * file states; one with no size a card. The small ones stand on a plank of their own (shelfOf).
   */
  ensureShelf() {
    if (this.shelf || !this.organelles.length || !this.layout) return this.shelf;
    const file = (this.model.raw.species || []).find((item) => item.id === this.species);
    const levels = Object.fromEntries((file?.levels || []).map((level) => [level.id, level]));
    const cell = { shape: levels.cell?.shape, parts: file?.cell?.parts || {}, has: () => true, neighbours: Boolean(levels.tissue), notes: [] };
    let models = new Map();
    try {
      // Only those with a size in hand are built: the others stand as cards.
      if (cell.shape) models = organelleModels(cell, this.organelles.filter((item) => item.size).map((item) => item.kind.id).filter((kind) => SHELF_MODELS[kind]));
    } catch (error) {
      console.warn(`the shelf's models could not be built: ${error.message}`);
    }
    const placed = [], made = new Map();
    for (const item of this.organelles) {
      const drawn = drawnSize(item.size);
      // No model in the Cell view, a size in hand: a simple model of its own (machines_shelf.js, SIMPLE), an illustration; a kind
      // with none there, a plain sphere, or a capsule where its size gives a length.
      const model = models.get(item.kind.id) || (drawn?.across && !SHELF_MODELS[item.kind.id] ? simpleModel(item.kind.id, { long: drawn.long ? drawn.long / drawn.across : 1 }) : null);
      const scale = model ? scaleFor(model, drawn) : null;
      if (!scale) {
        placed.push({ id: item.id, item });
        continue;
      }
      const size = model.box.getSize(new THREE.Vector3()).multiply(scale);
      made.set(item.id, { model, scale });
      placed.push({ id: item.id, item, w: size.x, d: size.z, h: size.y });
    }
    const layout = shelfOf(placed, this.layout.bounds);
    const root = new THREE.Group();
    root.userData.keep = true;
    // The shelf's plank, and the small organelles' own plank between it and the bench.
    for (const board of [layout.plank, layout.small?.plank].filter(Boolean)) {
      const plank = new THREE.Mesh(new THREE.BoxGeometry(board.w, SHELF.h, board.d), this.materials.bench);
      plank.position.set(board.x, -SHELF.h / 2, board.z);
      plank.userData.unpickable = true;
      root.add(plank);
    }
    const holders = new Map();
    for (const entry of layout.items) {
      const own = made.get(entry.id);
      if (own) {
        const { holder } = placeModel(own.model, { scale: own.scale, turn: FACING[entry.item.kind.id] || 0, at: new THREE.Vector3(entry.x, 0, entry.z) });
        holder.userData.pick = entry.id;
        paintModel(own.model, this.stage.palette || {});
        root.add(holder);
        holders.set(entry.id, { holder, model: own.model });
      } else {
        // No size in hand: a card of the shelf's own size, the same for all, not to scale.
        const card = new THREE.Mesh(new THREE.BoxGeometry(entry.w, entry.h, entry.d), new THREE.MeshStandardMaterial({ roughness: 0.42, metalness: 0.08 }));
        card.material.userData = { own: true, hue: SHELF_MODELS[entry.item.kind.id]?.hue || "ghost" };
        (this.shelfCards ??= new Set()).add(card.material);
        card.position.set(entry.x, entry.h / 2, entry.z);
        card.userData.pick = entry.id;
        root.add(card);
        holders.set(entry.id, { holder: card });
      }
    }
    this.shelf = { species: this.species, anchor: this.layout.bounds.minZ, count: this.organelles.length, layout, root, holders, models };
    this.root.add(root);
    this.views = null;
    if (this.stage.rig && this.active) this.stage.rig.limits = { ...this.stage.rig.limits, maxDistance: this.farthest() };
    this.applyColours();
    if (this.loupe) this.buildLoupe();
    this.placeShelfVisibility();
    return this.shelf;
  }

  dropShelf() {
    if (!this.shelf) return;
    this.root.remove(this.shelf.root);
    disposeTree(this.shelf.root);
    this.shelf = this.shelfCards = this.loupeGroup = this.loupeInfo = this.loupeBox = null;
    this.views = null;
  }

  /** How far the camera may go out: past the shelf's stop, or the bench's own limit where there is no shelf. */
  farthest() {
    const shelf = this.organelles.length ? this.shelfView() : null;
    return shelf ? Math.max(900, shelf.distance * 1.8) : 900;
  }

  /** The shelf is drawn only while the camera stands well out from the bench: at the bench's stop it is far out of the picture, and costs nothing. */
  placeShelfVisibility() {
    if (!this.shelf) return;
    const distance = this.stage.rig?.distance;
    // Drawn while the camera stands well out from the bench, while it travels up, while an organelle is chosen, and while it looks at
    // the shelf from any distance (a small organelle framed close brings it as near as the bench's own stop: 20 November 2026).
    this.shelf.root.visible = this.organelles.length > 0 && distance !== undefined && (distance > 1.6 * this.benchView().distance || Boolean(this.travel && this.travel.to.distance > this.travel.from.distance) || Boolean(organelleKind(this.selected)) || this.lookingAtShelf());
  }

  /** Whether the camera looks at the shelf or the small organelles' plank: its target lies behind the bench's back edge, where they stand. */
  lookingAtShelf() {
    const target = this.stage.rig?.target;
    return Boolean(this.shelf && this.layout && target && target.z < this.layout.bounds.minZ - (this.shelf.layout.small ? SHELF.small.gap : SHELF.gap) / 2);
  }

  /**
   * The views of the bench's, the small organelles' and the shelf's stops, for the screen as it is (kept until the insets, the
   * size or the layout change). The small organelles' stop is where they stand on a plank of their own, if there are any.
   */
  stopViews() {
    const key = `${JSON.stringify(this.stage.insets || {})}|${this.stage.width}x${this.stage.height}|${this.layout?.bounds.minZ}|${Boolean(this.shelf)}`;
    if (this.views?.key === key) return this.views;
    const bench = this.benchHome();
    let shelf = null, small = null;
    if (this.organelles.length && this.ensureShelf()) {
      const b = this.shelf.layout.bounds, near = this.layout.bounds.maxZ;
      // The whole shelf, and the bench before it: at the shelf's stop the bench is a small marked tray.
      shelf = this.fitOnScreen(new THREE.Box3(new THREE.Vector3(b.minX, 0, b.minZ), new THREE.Vector3(b.maxX, b.maxY, near)), 0.04);
      // The small organelles' plank, the bench before it: between the two.
      const s = this.shelf.layout.small?.bounds;
      if (s) small = this.fitOnScreen(new THREE.Box3(new THREE.Vector3(s.minX, 0, s.minZ), new THREE.Vector3(s.maxX, s.maxY, near)), 0.04);
      if (small && !(small.distance > bench.distance && small.distance < shelf.distance)) small = null; // a stop only where it stands between the two
    }
    this.views = { key, bench, small, shelf };
    return this.views;
  }

  benchView() {
    return this.stopViews().bench;
  }

  shelfView() {
    return this.stopViews().shelf;
  }

  /**
   * The view at a camera distance on the way between the bench and the shelf: its target moves from the bench's to the shelf's
   * as the distance grows, in step with it, so that what is left stays in the picture while what comes is seen arriving.
   * Nearer than the bench's stop it looks at what is chosen on the bench, or the bench's middle.
   */
  pathView(distance) {
    const { bench, small, shelf } = this.stopViews();
    if (!shelf || distance <= bench.distance) {
      const chosen = this.layout?.items.find((item) => item.id === this.selected);
      const target = distance < bench.distance && chosen ? new THREE.Vector3(chosen.x, chosen.y + chosen.h / 2, chosen.z) : bench.target.clone();
      return { ...bench, target, distance };
    }
    // From one stop to the next: the bench, the small organelles' plank where there is one, the shelf.
    const [from, to] = small && distance < small.distance ? [bench, small] : small ? [small, shelf] : [bench, shelf];
    const along = Math.min(1, (distance - from.distance) / Math.max(1e-6, to.distance - from.distance));
    return { ...bench, target: from.target.clone().lerp(to.target, along), distance };
  }

  /** The page's scale bar at a camera distance, by the page's own rule (ui/viewer.js, updateScaleBar): its length, in nanometres. */
  barAt(distance) {
    const height = this.stage.height || 900, half = Math.tan(((this.stage.camera?.fov || 34) * Math.PI) / 360);
    const perMicron = height / (2 * distance * half) / (UNIT_NM / 1000);
    const most = 150 / perMicron, power = Math.pow(10, Math.floor(Math.log10(most)));
    return Math.round(([5, 2, 1].map((step) => step * power).find((value) => value <= most) ?? power) * 1000 * 1000) / 1000;
  }

  /** The camera's distance at which the page's scale bar reads `nm`, the bar's room holding one and a half of it. */
  distanceForBar(nm) {
    const height = this.stage.height || 900, half = Math.tan(((this.stage.camera?.fov || 34) * Math.PI) / 360);
    const perUnit = (150 / ((1.5 * nm) / 1000)) * (UNIT_NM / 1000);
    return height / (2 * half * perUnit);
  }

  /**
   * The rail's stops, largest first: the shelf and the bench by name, each with what the scale bar reads there; the powers of
   * ten from 10 µm to 10 nm (where a named stop reads the same, the named one stands for it); and a mark for what is chosen,
   * at its own size.
   */
  stops() {
    const { bench, small, shelf } = this.stopViews();
    const named = [{ id: "bench", distance: bench.distance, name: "The bench" }, ...(small ? [{ id: "small", distance: small.distance, name: "Small organelles" }] : []), ...(shelf ? [{ id: "shelf", distance: shelf.distance, name: "The shelf" }] : [])].map((stop) => ({ ...stop, bar: this.barAt(stop.distance) }));
    const powers = POWERS.map((nm) => ({ id: `nm${nm}`, distance: this.distanceForBar(nm), bar: nm })).filter((stop) => !named.some((other) => other.bar === stop.bar));
    const chosen = this.chosenStop();
    return [...named, ...powers, ...(chosen ? [chosen] : [])].sort((a, b) => b.distance - a.distance);
  }

  /** The mark for what is chosen: an organelle or a machine drawn to scale, at its own size; null for anything else. */
  chosenStop() {
    const id = this.selected;
    if (!id || id === BENCH_ID) return null;
    const organelle = this.shelf?.layout.items.find((item) => item.id === id);
    if (organelle?.type === "shape") return { id: "chosen", distance: this.organelleView(id).distance, name: `Chosen: ${organelle.item.label}`, size: Math.max(organelle.w, organelle.h) * UNIT_NM };
    const entry = this.layout?.items.find((item) => item.id === id);
    if (entry?.type === "shape") return { id: "chosen", distance: Math.max(2.5, this.fitOnScreen(this.focusBox(entry), 0.1).distance), name: `Chosen: ${entry.item.label}`, size: Math.max(entry.w, entry.h, entry.d) * UNIT_NM };
    return null;
  }

  /** The stop nearest the camera, on a scale of powers of ten. */
  nearestStop() {
    const distance = this.stage.rig?.distance;
    if (!distance || !this.layout) return "bench";
    let best = null, gap = Infinity;
    for (const stop of this.stops()) {
      const off = Math.abs(Math.log(distance / stop.distance));
      if (off < gap) [best, gap] = [stop.id, off];
    }
    return best;
  }

  /** The rail's button for each stop: its words, and what pressing it does, in a sentence. */
  railOf() {
    return this.stops().map((stop) => ({
      id: stop.id,
      label: stop.name ? `${stop.name} · ${lengthWords(stop.size ?? stop.bar)}` : lengthWords(stop.bar),
      title: stop.id === "chosen" ? `Travel to what you chose, at its own size (${lengthWords(stop.size)} at its longest)` : stop.id === "shelf" ? `Travel up to the shelf of organelles, where the scale bar reads ${lengthWords(stop.bar)}` : stop.id === "small" ? `Travel to the small organelles on their own plank, where the scale bar reads ${lengthWords(stop.bar)}` : stop.id === "bench" ? `Travel to the bench of machines, where the scale bar reads ${lengthWords(stop.bar)}` : `Travel to where the scale bar reads ${lengthWords(stop.bar)}`,
    }));
  }

  /** A stop of the rail (or `scale=` in the address): the camera travels there, the same time for each power of ten; at once with less motion. */
  goToScale(id, immediate = false) {
    if (id === "chosen") {
      if (this.selected) this.focus(this.selected);
      return;
    }
    if (!["bench", "small", "shelf"].includes(id) && !/^nm\d+$/.test(id || "")) return;
    this.endLoupe(); // a stop of the rail leaves the loupe
    this.focused = null; // and supersedes a framing still waiting on a panel's insets (a phone's sheet closing after a choice)
    this.stop = id;
    if (this.active) this.travelTo(this.homeView(), { immediate });
    this.onChrome?.();
  }

  /** The camera goes to a view: at once with less motion (or for a still picture), else a travel whose time is the same for each power of ten. */
  travelTo(view, { immediate = false } = {}) {
    const rig = this.stage.rig;
    if (!rig || !view) return;
    this.homeHeld = null;
    if (view.distance > 1.6 * this.benchView().distance) this.ensureShelf();
    if (immediate || this.stage.reducedMotion || rig.instant || !rig.view) {
      this.travel = null;
      rig.setView(view);
      this.afterMove();
      return;
    }
    const from = rig.view();
    let turn = (view.azimuth - from.azimuth) % (Math.PI * 2);
    if (turn > Math.PI) turn -= Math.PI * 2;
    if (turn < -Math.PI) turn += Math.PI * 2;
    const powers = Math.abs(Math.log10(view.distance / from.distance));
    const across = from.target.distanceTo(view.target) / Math.max(from.distance, view.distance);
    this.travel = { from, to: { ...view, target: view.target.clone(), azimuth: from.azimuth + turn }, elapsed: 0, duration: Math.max(450, PER_POWER * powers, 700 * Math.min(1, across)) };
    rig.flight = null;
    this.placeShelfVisibility();
    this.stage.invalidate?.();
  }

  /** One step of a travel: the distance moves evenly in powers of ten, and the target with it. Returns whether it goes on. */
  stepTravel(dt) {
    const travel = this.travel, rig = this.stage.rig;
    if (!travel || !rig) return false;
    if (rig.pointers?.size && rig.dragged) {
      this.travel = null; // the visitor took the camera (a press alone, which may have started the travel, does not stop it)
      return false;
    }
    travel.elapsed += dt;
    const t = Math.min(1, travel.elapsed / travel.duration), eased = t * t * (3 - 2 * t);
    const { from, to } = travel;
    const distance = Math.exp(Math.log(from.distance) * (1 - eased) + Math.log(to.distance) * eased);
    const along = Math.abs(to.distance - from.distance) > 1e-6 * to.distance ? (distance - from.distance) / (to.distance - from.distance) : eased;
    rig.setView({ target: from.target.clone().lerp(to.target, along), distance, azimuth: from.azimuth + (to.azimuth - from.azimuth) * eased, polar: from.polar + (to.polar - from.polar) * eased });
    if (t >= 1) this.travel = null;
    return true;
  }

  /** After the camera moved: the shelf drawn or not, the names that belong to where the camera stands, and the rail's mark. */
  afterMove() {
    const distance = this.stage.rig?.distance || 0;
    this.lastDistance = distance;
    this.placeShelfVisibility();
    const { bench, small, shelf } = this.layout ? this.stopViews() : {};
    // Which stop's names the picture shows: the one whose distance is nearest on a scale of powers of ten; with the loupe held, or
    // an organelle chosen and looked at, its own plank's; looking at the shelf's plank, the shelf's; looking at the small organelles'
    // plank from nearer than its stop, theirs (a small organelle framed close brings the camera as near as the bench's stop).
    const looked = shelf && this.lookingAtShelf() ? this.lookedPlank() : null;
    const closest = (...stops) => stops.filter(Boolean).sort((a, b) => Math.abs(Math.log(distance / a[1])) - Math.abs(Math.log(distance / b[1])))[0]?.[0];
    const held = this.loupe ? "shelf" : looked && organelleKind(this.selected) ? this.plankOf(this.selected) : null;
    const band = !shelf ? "bench" : held || (looked === "shelf" && !this.travel ? "shelf" : looked === "small" && distance < (small || shelf).distance ? "small" : closest(["bench", bench.distance], small && ["small", small.distance], ["shelf", shelf.distance]));
    if (band !== this.band) {
      this.band = band;
      this.buildLabels();
    }
    const nearest = this.nearestStop();
    if (nearest !== this.railActive) {
      this.railActive = nearest;
      this.onChrome?.();
    }
  }

  /** The plank the camera looks at, by its target: the small organelles' (from the bench's back edge to their plank's back), else the shelf's. */
  lookedPlank() {
    const target = this.stage.rig?.target, small = this.shelf?.layout.small;
    return small && target && target.z >= small.bounds.minZ - SHELF.gap / 2 ? "small" : "shelf";
  }

  /** The view that frames an organelle on the shelf, with the loupe beside it where one is held there. */
  organelleView(id) {
    const entry = this.ensureShelf()?.layout.items.find((item) => item.id === id);
    if (!entry) return this.shelfView() || this.benchView();
    const box = new THREE.Box3(new THREE.Vector3(entry.x - entry.w / 2, 0, entry.z - entry.d / 2), new THREE.Vector3(entry.x + entry.w / 2, entry.h, entry.z + entry.d / 2));
    // On a phone, where a sheet takes the lower half, a loupe held there is framed by itself: the speck and the lens, the organelle behind them.
    if (this.loupe?.organelle === id && this.loupeBox && (this.stage.width || 1600) < 760) return this.fitOnScreen(this.loupeBox.clone().expandByScalar(this.loupeInfo?.radius || 60), 0.08);
    if (this.loupe?.organelle === id && this.loupeBox) box.union(this.loupeBox);
    box.expandByScalar(Math.max(entry.w, entry.h) * 0.12);
    return this.fitOnScreen(box, 0.08);
  }

  /** A machine drawn from its own file, at the level it is shown at: an outline among the others, its parts when chosen. */
  buildMachineAt(entry, holder) {
    const data = this.machines.get(entry.id);
    if (!data) {
      this.readMachine(entry);
      return;
    }
    const level = this.selected === entry.id ? this.level : 1;
    const ids = new Set();
    const layers = new Set((data.layers || []).map((layer) => `${PREFIX}${data.id}:${layer.id}`));
    const ctx = {
      material: (role) => {
        const [hue, opacity, glass] = ROLE_HUE[role] || ROLE_HUE.rotor;
        const material = new THREE.MeshStandardMaterial({ roughness: glass ? 0.3 : 0.5, metalness: 0, transparent: opacity < 1, opacity, depthWrite: !glass, side: glass ? THREE.DoubleSide : THREE.FrontSide });
        material.userData = { own: true, hue, role };
        return material;
      },
      add: (object, id) => {
        // Among the other machines the envelope it sits in is left out: the trays are not a cell. Its parts are chosen under their own ids.
        if (layers.has(id)) object.visible = level >= 2;
        if (id && level >= 2) {
          object.userData.pick = id;
          ids.add(id);
        } else object.userData.unpickable = level >= 2 && !id;
      },
    };
    const built = buildMachine(ctx, data, { level });
    const group = new THREE.Group();
    group.add(built.root || built);
    group.scale.setScalar(MACHINE_SCALE);
    // Standing on the tray: its lowest point on the tray's floor, its axis up.
    const box = new THREE.Box3();
    group.updateMatrixWorld(true);
    group.traverseVisible((object) => object.isMesh && box.expandByObject(object));
    if (!box.isEmpty()) group.position.y = -box.min.y;
    holder.add(group);
    this.paint(group);
    this.built.set(entry.id, { level, ids, group });
    if (!this.measured[entry.id] && !box.isEmpty()) {
      const size = box.getSize(new THREE.Vector3());
      this.measured[entry.id] = { w: Math.max(size.x, 1), d: Math.max(size.z, 1), h: Math.max(size.y, 1) };
      this.relayout = true; // laid out again with its true size, at the next frame
    }
  }

  /**
   * A machine measured from a structure: each body an ellipsoid at its measured size, centre and axes. Among the others
   * the bodies are one outline in the group's colour; chosen (level 2), each is a part of its own, in its own shade.
   */
  /**
   * Every measured machine's outline, among the others: one instanced mesh of ellipsoids for the whole bench, so that
   * a bench of many machines costs one draw (a chosen machine's own bodies are drawn apart, and its outline is hidden).
   */
  buildOutlines() {
    const items = [];
    for (const { entry } of this.shapeMeshes.values()) {
      if (entry.shape.kind !== "measured") continue;
      const offset = this.standOffset(entry.shape);
      for (const body of bodiesAt(entry.shape, 1)) items.push({ id: entry.id, group: entry.group, entry, body, offset });
    }
    this.outlineItems = items;
    if (this.outlines) this.root.remove(this.outlines);
    // Coarser than a chosen machine's bodies: seen from the opening view, a few pixels across; and coarser still on a bench
    // of many bodies, so that the outlines stay within about 30,000 triangles (a phone's share of the frame).
    const detail = [[16, 12], [12, 9], [10, 8], [8, 6]].find(([across, down]) => items.length * across * down * 2 <= 30000) || [8, 6];
    if (this.outlineDetail?.join() !== detail.join()) {
      this.outlineGeometry?.dispose();
      this.outlineGeometry = new THREE.SphereGeometry(0.5, ...detail);
      this.outlineDetail = detail;
    }
    const ball = this.outlineGeometry;
    const mesh = new THREE.InstancedMesh(ball, this.materials.outline ??= new THREE.MeshStandardMaterial({ roughness: 0.38, metalness: 0.06, envMapIntensity: 1 }), Math.max(1, items.length));
    mesh.count = items.length;
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, items.length) * 3).fill(1), 3);
    mesh.userData.pick = (hit) => items[hit.instanceId]?.id || null;
    this.outlines = mesh;
    this.root.add(mesh);
    this.placeOutlines();
  }

  /** Where a measured machine's frame stands in its holder: its lowest point on the tray's floor, centred on its place. */
  standOffset(shape) {
    return new THREE.Vector3(-(shape.lo[0] + shape.hi[0]) / 2, -shape.lo[1], -(shape.lo[2] + shape.hi[2]) / 2);
  }

  /** The outline instances at their places; a chosen machine's are hidden, its own bodies drawn instead. */
  placeOutlines() {
    const mesh = this.outlines;
    if (!mesh) return;
    const matrix = new THREE.Matrix4(), turn = new THREE.Quaternion(), place = new THREE.Vector3(), size = new THREE.Vector3();
    this.outlineItems.forEach((item, index) => {
      const shown = this.shapeMeshes.get(item.id)?.entry;
      if (item.id === this.selected || !shown) {
        mesh.setMatrixAt(index, matrix.makeScale(0, 0, 0));
        return;
      }
      const [a, b, c] = item.body.axes.map((axis) => new THREE.Vector3(...axis));
      turn.setFromRotationMatrix(new THREE.Matrix4().makeBasis(a, b, c));
      // At its place at rest: an outline does not rise (only the chosen machine does, drawn by its own bodies).
      place.set(...item.body.centre_nm.map((n) => n / UNIT_NM)).add(item.offset).add(new THREE.Vector3(shown.x, shown.y, shown.z));
      size.set(...item.body.across_nm.map((n) => n / UNIT_NM));
      mesh.setMatrixAt(index, matrix.compose(place, turn, size));
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
  }

  buildMeasuredAt(entry, holder) {
    const shape = entry.shape;
    // Among the others a measured machine is drawn by the bench's instanced outlines (buildOutlines); only when chosen
    // does it have bodies of its own: its outline lit, its parts or its chains, each in its hue or shade. They are one
    // instanced mesh, so that a machine of many chains costs one draw; each body is picked by its instance.
    if (this.selected !== entry.id) {
      this.built.set(entry.id, { level: 1, ids: new Set(), group: null, measured: true });
      return;
    }
    const surface = this.level === SHAPE_LEVEL ? entry.item.size?.surface : null;
    // At Shape, the ellipsoids of the level before stand until the surfaces are read (and stay where they cannot be).
    const level = surface ? 3 : this.level;
    const group = new THREE.Group(), ids = new Set();
    // A chain wears the hue of the named part that holds it (by its entity or by its chain), where the overlay gives that part one.
    const partOf = (body) => (body.entity || body.chain || String(body.id || "").startsWith("chain-") ? partOfChain(shape, body) : null);
    const bodies = bodiesAt(shape, level).map((body) => ({ ...body, hue: body.hue || partOf(body)?.hue || null }));
    // Its bodies' spheres: as smooth as a chosen machine's are, and coarser where it has many bodies (the mitochondrial
    // ribosome's 89 chains), so that a chosen machine at any level stays within about 12,000 triangles on any bench.
    const ball = this.bodyBall(bodies.length);
    const entities = [...new Set(bodies.map((body) => body.entity).filter(Boolean))];
    // Its shade. At Parts, a part drawn as its chains is one colour: its hue, or the group's in one of two shades by
    // part. At Subunits, by its kind of chain where the entry has several; where it has one, by the part that holds
    // it, with neighbours a little apart, so that the parts and the chains of a machine of one kind of chain are told apart.
    const shadeOf = (body, index) => {
      if (level < 2) return 0;
      if (level === 2 && body.part) return body.hue ? 0 : shape.parts.findIndex((part) => part.id === body.part) % 2 ? 1 : 0;
      if (entities.length > 1 && body.entity) return entities.indexOf(body.entity) / (entities.length - 1);
      if (body.entity) return (shape.parts.indexOf(partOf(body)) % 2 ? 0.7 : 0) + (index % 2) * 0.3;
      return body.hue ? 0 : index % 2 ? 1 : 0;
    };
    // What a body is chosen as: at Parts, its part (a chain's body carries its part's id); at Subunits, itself.
    const pickOf = (body) => (level < 2 ? null : body.part ? `${entry.id}:${body.part}` : body.id ? `${entry.id}:${body.id}` : null);
    const material = level >= 2 ? new THREE.MeshStandardMaterial({ roughness: 0.42, metalness: 0.05, envMapIntensity: 1 }) : this.materials.lit;
    if (level >= 2) material.userData = { own: true, bodies: true };
    const mesh = new THREE.InstancedMesh(ball, material, bodies.length);
    const matrix = new THREE.Matrix4(), turn = new THREE.Quaternion();
    bodies.forEach((body, index) => {
      const [a, b, c] = body.axes.map((axis) => new THREE.Vector3(...axis));
      turn.setFromRotationMatrix(new THREE.Matrix4().makeBasis(a, b, c));
      mesh.setMatrixAt(index, matrix.compose(new THREE.Vector3(...body.centre_nm.map((n) => n / UNIT_NM)), turn, new THREE.Vector3(...body.across_nm.map((n) => n / UNIT_NM))));
      if (pickOf(body)) ids.add(pickOf(body));
    });
    mesh.computeBoundingSphere();
    mesh.userData.bodies = bodies.map((body, index) => ({ id: pickOf(body), hue: body.hue, shade: shadeOf(body, index) }));
    if (level >= 2) {
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(bodies.length * 3).fill(1), 3);
      mesh.userData.pick = (hit) => mesh.userData.bodies[hit.instanceId]?.id || entry.id;
    }
    group.add(mesh);
    // Where its membrane lies, where the measure gives it: the ring's own extent along the machine's axis (illustration).
    if (shape.membrane && level >= 2) group.add(this.membraneSlab(entry));
    group.position.copy(this.standOffset(shape));
    holder.add(group);
    const built = { level: surface ? SHAPE_LEVEL : level, ids, group, bodies: mesh, measured: true };
    this.built.set(entry.id, built);
    this.shadeParts(entry.id);
    if (surface) this.drawSurface(entry, built, surface);
  }

  /**
   * The Shape level: the machine's shape file (schema/MACHINE_SHAPES.md), asked for only where the catalogue says one is
   * published, read once and kept; drawn by machine_shape.js as one mesh in the group that holds the ellipsoids, so that
   * it sits where they sit. A surface is chosen as its chain (where the catalogue names the machine's chains) or its part.
   * Where the file cannot be read, the ellipsoids stay and the panel says why.
   */
  async drawSurface(entry, built, surface) {
    const found = await (this.surfaces ??= new Map()).get(surface.file) || (await loadShape(surface.file));
    if (found.status === "found") this.surfaces.set(surface.file, found);
    if (this.built.get(entry.id) !== built || this.disposed) return; // chosen otherwise meanwhile
    if (found.status !== "found") {
      built.surfaceWords = found.words;
      this.catalogue.shapeWords.set(surface.file, found.words);
      this.onChrome?.();
      this.onOpen?.();
      return;
    }
    const shape = entry.shape, chains = new Set(shape.chains.map((chain) => chain.id));
    // A machine of the catalogue by its kind; a unit of the law inventory by its own page id. A ribosome's subunits as two
    // solids; `surfaceTones` (not offered on the page) draws their RNA and protein apart, for a look.
    const kind = kindOf(entry.id);
    const drawn = buildShape(found.data, { ...(kind ? { kind } : { id: entry.id }), perNm: 1 / UNIT_NM, colour: this.surfaceColour(entry), tones: Boolean(this.surfaceTones) });
    // What a surface is chosen as: its chain, where the catalogue names the chains; else its part; else the machine.
    const idOf = (row) => (row?.chain && chains.has(row.id) ? row.chain : row?.part || null);
    drawn.mesh.userData.pick = (hit) => idOf(drawn.surfaceAt(hit.faceIndex)) || entry.id;
    built.ids = new Set(drawn.surfaces.map(idOf).filter(Boolean));
    built.surface = drawn;
    built.surfaceIdOf = idOf;
    built.bodies.visible = false;
    built.group.add(drawn.mesh);
    this.shadeParts(entry.id);
    this.stage.invalidate?.();
    this.onChrome?.();
  }

  /** The colour of a surface: its part's hue as at Parts (or the group's, in two shades by part), its chains a little apart. */
  surfaceColour(entry) {
    const palette = this.stage.palette || {}, shape = entry.shape;
    const ground = new THREE.Color(palette.bg || "#ffffff");
    const seen = new Map();
    const chainHues = new Map(shape.chains.filter((chain) => chain.hue).map((chain) => [chain.id, chain.hue]));
    return (partId, kind, row) => {
      const chainColour = palette[chainHues.get(row.id)];
      if (chainColour) return new THREE.Color(chainColour);
      const index = shape.parts.findIndex((part) => part.id === partId);
      const part = shape.parts[index];
      const base = new THREE.Color(palette[part?.hue] || palette[GROUP_HUE[entry.group]] || palette.ghost || "#888888");
      const within = seen.get(partId) ?? new Map();
      seen.set(partId, within);
      if (!within.has(row.id)) within.set(row.id, within.size);
      const apart = (within.get(row.id) % 2) * 0.18 + (kind === "nucleic" ? 0.35 : 0);
      return base.lerp(ground, Math.min(0.8, (part?.hue ? 0 : index % 2 ? 0.45 : 0) + apart));
    };
  }

  /** A sphere for a chosen machine's bodies, the finest that keeps them within about 12,000 triangles together. */
  bodyBall(count) {
    const detail = [[24, 16], [16, 12], [12, 9], [10, 8], [8, 6]].find(([across, down]) => count * across * down * 2 <= 12000) || [8, 6];
    this.bodyBalls ??= new Map();
    if (!this.bodyBalls.has(detail.join())) this.bodyBalls.set(detail.join(), new THREE.SphereGeometry(0.5, ...detail));
    return this.bodyBalls.get(detail.join());
  }

  /** The colour each body of a chosen measured machine wears, as hex (for the checks). */
  bodyColours(id) {
    const mesh = this.built?.get(id)?.bodies;
    if (!mesh) return [];
    const colour = new THREE.Color();
    return mesh.userData.bodies.map((_, index) => {
      if (mesh.instanceColor) mesh.getColorAt(index, colour);
      else colour.copy(mesh.material.color);
      return colour.getHexString();
    });
  }

  /**
   * A thin slab where the machine's membrane lies: as thick as the atoms of its part in the membrane reach along the
   * machine's axis, centred on that part (machines_layout.js, membraneOf); across, the room of its tray round it (clear of the tray's other machines and of the
   * name along its front), at most three times the machine's width each way. An illustration, labelled so.
   */
  membraneSlab(entry) {
    const shape = entry.shape;
    const membrane = membraneOf(shape);
    const reach = membrane.thick_nm / UNIT_NM / 2, middle = membrane.centre_nm / UNIT_NM;
    const tray = this.layout.trays.find((value) => value.group === entry.group);
    const rim = 0.45 + 0.25, most = 3 * Math.max(shape.w, shape.d);
    const room = {
      x0: Math.max(tray.x - tray.w / 2 + rim, entry.x - most), x1: Math.min(tray.x + tray.w / 2 - rim, entry.x + most),
      z0: Math.max(tray.z - tray.d / 2 + rim, entry.z - most), z1: Math.min(tray.z + tray.d / 2 - tray.head, entry.z + most),
    };
    for (const other of this.layout.items) {
      if (other.id === entry.id || other.group !== entry.group) continue;
      const gap = 0.3;
      if (other.x - other.w / 2 >= entry.x + entry.w / 2) room.x1 = Math.min(room.x1, other.x - other.w / 2 - gap);
      else if (other.x + other.w / 2 <= entry.x - entry.w / 2) room.x0 = Math.max(room.x0, other.x + other.w / 2 + gap);
      else if (other.z - other.d / 2 >= entry.z + entry.d / 2) room.z1 = Math.min(room.z1, other.z - other.d / 2 - gap);
      else if (other.z + other.d / 2 <= entry.z - entry.d / 2) room.z0 = Math.max(room.z0, other.z + other.d / 2 + gap);
    }
    const slab = new THREE.Mesh(new THREE.BoxGeometry(room.x1 - room.x0, 2 * reach, room.z1 - room.z0), this.materials.membrane ??= new THREE.MeshStandardMaterial({ roughness: 0.3, metalness: 0, transparent: true, opacity: 0.24, depthWrite: false, side: THREE.DoubleSide }));
    this.materials.membrane.userData = { slab: true };
    // In the machine's group, which stands at its place (the holder's) moved by its stand offset.
    const offset = this.standOffset(shape);
    slab.position.set((room.x0 + room.x1) / 2 - entry.x - offset.x, middle, (room.z0 + room.z1) / 2 - entry.z - offset.z);
    slab.userData.unpickable = true;
    slab.userData.slab = true;
    // Its label stands on its top, just in front of the machine and to its left, where the panel does not cover it.
    slab.userData.anchor = new THREE.Vector3(Math.max(room.x0 + 0.4, entry.x - shape.w), entry.y + offset.y + middle + reach, Math.min(room.z1 - 0.4, entry.z + shape.d));
    return slab;
  }

  /** The bodies of a chosen measured machine: a part in its own hue where the overlay gives one, else a shade of the group's colour. */
  shadeParts(id) {
    const built = this.built?.get(id), palette = this.stage.palette || {};
    if (!built?.measured || built.level < 2 || !built.bodies) return;
    const ground = new THREE.Color(palette.bg || "#ffffff");
    const group = this.shapeMeshes.get(id)?.entry.group;
    const mesh = built.bodies;
    // The part or chain chosen in it is lit in the page's accent, as the chosen machine is, so that it is told apart.
    const chosen = this.selected === id ? this.selectedPart : null;
    const lit = new THREE.Color(palette.accent || "#1f6fd0");
    mesh.material.color.set(0xffffff);
    mesh.userData.bodies.forEach((look, index) => {
      const base = new THREE.Color(palette[look.hue] || palette[GROUP_HUE[group]] || palette.ghost || "#888888");
      mesh.setColorAt(index, chosen && look.id === chosen ? lit : base.lerp(ground, (look.hue ? 0.3 : 0.45) * Math.min(1, look.shade)));
    });
    mesh.instanceColor.needsUpdate = true;
    if (built.surface) {
      built.surface.recolour();
      if (chosen) for (const row of built.surface.surfaces) if (built.surfaceIdOf(row) === chosen) built.surface.recolour(row, lit);
    }
    for (const child of built.group.children) if (child.userData.slab) child.material.color.set(palette.bioMembrane || "#2fb3a3");
  }

  /** Reads a machine's file from beside the page (as its closer view does), then builds it where it stands. */
  readMachine(entry) {
    if (this.reading?.has(entry.id)) return;
    (this.reading ??= new Set()).add(entry.id);
    loadBeside(entry.shape.file)
      .then((data) => {
        this.machines.set(entry.id, data);
        this.reading.delete(entry.id);
        const shown = this.shapeMeshes?.get(entry.id);
        if (shown) this.buildMachineAt(shown.entry, shown.holder);
        this.stage.invalidate?.();
      })
      .catch(() => this.reading.delete(entry.id));
  }

  /** The machine file's materials take their colours from the palette, as the other shapes do. */
  paint(group) {
    const palette = this.stage.palette || {};
    group.traverse((object) => {
      const material = object.material;
      if (material?.userData?.hue && palette[material.userData.hue]) material.color.set(palette[material.userData.hue]);
    });
  }

  placeCards() {
    const dummy = new THREE.Object3D();
    this.cardList.forEach((entry, index) => {
      const lift = this.lifts.get(entry.id) || 0;
      dummy.position.set(entry.x, entry.y + entry.h / 2 + lift, entry.z);
      dummy.scale.set(entry.w, entry.h, entry.d);
      dummy.updateMatrix();
      this.cardBody.setMatrixAt(index, dummy.matrix);
      dummy.position.set(entry.x - entry.w / 2 + 0.55, entry.y + entry.h / 2 + 0.03 + lift, entry.z);
      dummy.scale.set(0.9, entry.h + 0.06, entry.d - 0.2);
      dummy.updateMatrix();
      this.cardTab.setMatrixAt(index, dummy.matrix);
    });
    this.cardBody.instanceMatrix.needsUpdate = this.cardTab.instanceMatrix.needsUpdate = true;
    this.cardBody.computeBoundingSphere();
    this.cardTab.computeBoundingSphere();
  }

  writeNames() {
    const palette = this.stage.palette || {};
    if (this.flatNames) {
      this.root.remove(this.flatNames);
      this.flatNames.material.map?.dispose();
      this.flatNames.material.dispose();
      this.flatNames.geometry.dispose();
    }
    const plaques = [];
    const fit = (text, width, most) => Math.min(most, width / Math.max(1, text.length * 0.56));
    for (const entry of this.cardList) {
      const text = entry.item.short || entry.item.label;
      // Written on the card as it lies: a card that rises (chosen) is named by the page's label above it, so the names are not written again each frame.
      // A machine its species' records do not name, only its dossier's family route, says so on its face, in words.
      const rows = byFamily(entry.item) ? entry.item.entry.gathered?.looked_for || [] : null;
      if (!rows) {
        plaques.push({ text, x: entry.x + 0.55, y: -entry.z, z: entry.y + entry.h + 0.02, h: fit(text, entry.w - 1.6, 1.15), align: "center", tone: "strong" });
        continue;
      }
      const lines = [`candidates for ${rows.filter((row) => row[2] === "candidates").length} of ${rows.length} ${rows.length === 1 ? "part" : "parts"},`, "by family"];
      plaques.push({ text, x: entry.x + 0.55, y: -(entry.z - 0.55), z: entry.y + entry.h + 0.02, h: fit(text, entry.w - 1.6, 1.0), align: "center", tone: "strong" });
      const small = Math.min(...lines.map((line) => fit(line, entry.w - 1.6, 0.55)));
      lines.forEach((line, index) => plaques.push({ text: line, x: entry.x + 0.55, y: -(entry.z + 0.45 + index * 0.62), z: entry.y + entry.h + 0.02, h: small, align: "center", tone: "soft" }));
    }
    // Each tray's name in its strip along the front, in one line or two.
    for (const tray of this.layout.trays) {
      tray.lines.forEach((line, index) => {
        const top = tray.z + tray.d / 2 - tray.head + 0.4 + TRAY.name * 0.5;
        plaques.push({ text: line, x: tray.x - tray.w / 2 + 0.9, y: -(top + index * TRAY.name * 1.25), z: 0.32, h: TRAY.name, align: "left", tone: "strong" });
      });
    }
    if (this.layout.scale) plaques.push({ text: `${this.layout.scale.nm} nm`, x: this.layout.scale.x + this.layout.scale.length + 0.8, y: -this.layout.scale.z, z: 0.02, h: 1.1, align: "left", tone: "soft" });
    this.plaques = plaques; // what is written on the bench, in words (the tests read it)
    this.flatNames = plaqueMesh(plaques, palette);
    if (this.flatNames) {
      this.flatNames.rotation.x = -Math.PI / 2;
      this.flatNames.material.transparent = true;
      this.flatNames.material.opacity = this.benchChoice() ? 0.12 : 1;
      this.root.add(this.flatNames);
    }
  }

  /** After a build while the view is shown: its labels, and its opening view where nothing is chosen. */
  afterBuild(reframe) {
    this.buildLabels();
    this.refresh();
    if (reframe && !this.selected) this.stage.rig?.setView(this.homeView());
  }

  // ------------------------------------------------------------ the lens interface

  /** A machine of the species shown or one of its parts; or a machine of the catalogue the species lacks, whose panel says which species have it. */
  has(id) {
    if (!id) return false;
    if (id === BENCH_ID) return Boolean(this.layout);
    if (organelleKind(id)) return Boolean(this.item(id));
    if (this.item(id) || this.partOf(id) || this.measuredPart(id)) return true;
    const kind = kindOf(id);
    return Boolean(this.catalogue && (kind ? id === `${PREFIX}${kind}` && this.catalogue.kinds.has(kind) : this.catalogue.speciesWith(id).length));
  }

  describe(id) {
    if (id === BENCH_ID) return this.describeBench();
    if (organelleKind(id)) {
      const panel = describeItem(this.catalogue, this.species, id, { scene: this.model.raw, drawn: this.drawnWords(id) });
      return panel ? { ...panel, doors: this.withLoupeDoors(panel.doors, id) } : null;
    }
    const owner = this.partOf(id);
    if (owner && this.built.get(owner)?.measured) return describePart(this.catalogue, this.species, owner, id.slice(owner.length + 1), { scene: this.model.raw });
    // A measured part named before its machine shows it (an address): its panel all the same.
    const asked = owner ? null : this.measuredPart(id);
    if (asked) return describePart(this.catalogue, this.species, asked.owner, id.slice(asked.owner.length + 1), { scene: this.model.raw });
    if (owner) {
      const data = this.machines.get(owner);
      const panel = describeMachinePart(data, id.split(":").at(-1), { species: (this.model.raw.species || []).find((item) => item.id === this.species) || null });
      return panel ? { ...panel, doors: [...(panel.doors || []), { label: "Back to the machine", lens: "machines", value: owner }] } : null;
    }
    const built = this.built?.get(id);
    const panel = describeItem(this.catalogue, this.species, id, { scene: this.model.raw, level: built?.level ?? null });
    // Where its shape file could not be read, its "Its shape" line says why instead (the card's words say what it is).
    if (panel && built?.surfaceWords) panel.facts = (panel.facts || []).map((fact) => (fact[0] === "Its shape" ? ["Its shape", built.surfaceWords] : fact));
    return panel ? { ...panel, doors: this.withLoupeDoors(panel.doors, id) } : panel;
  }

  /** A panel's doors with the loupe's: its way back first while a machine is held, else the way in after the panel's own. */
  withLoupeDoors(doors = [], id) {
    const loupe = this.loupeDoors(id);
    return loupe[0]?.value === "loupe:off" ? [...loupe, ...doors] : [...doors, ...loupe];
  }

  /** How an organelle is drawn, in words: the Cell view's own model of it, and which of its widths the paper's size sets. */
  drawnWords(id) {
    const item = this.item(id), model = SHELF_MODELS[item?.kind?.id], simple = SIMPLE[item?.kind?.id];
    const plank = item?.size && this.plankOf(id) === "small" ? " It stands on the small organelles' own plank, between the bench and the shelf." : "";
    // The Cell view has no model of it: a simple model of its own (machines_shelf.js), whose every part but the size is the picture's choice.
    if (!model && simple && item?.size) return `${simple.words.charAt(0).toUpperCase()}${simple.words.slice(1)}, at the size above: a simple model of its own, since the Cell view has none; ${simple.choice}. An illustration, at the bench's one scale.${plank}`;
    if (!model && item?.size) return `A plain ${item.size.long_um ? "capsule" : "sphere"} at the size above: the Cell view has no model of it. An illustration, at the bench's one scale.${plank}`;
    if (!model) return item ? (simple ? `No size in hand: a card on the shelf, not to scale. With a size it would stand as ${simple.words}, a simple model of its own, since the Cell view has none.` : "No model of it in the Cell view: a card on the shelf, not to scale.") : null;
    if (!item.size) return `No size in hand: a card on the shelf, not to scale. The Cell view draws it as ${model.words}.`;
    const sets = {
      across: "scaled as a whole so that it is as wide as the size above; its parts within it keep the Cell view's proportions, which are the picture's choice",
      thick: "scaled as a whole so that its sheets are as thick as the size above; how many sheets, how tall, how far apart and how they fold are the picture's choice",
      cisterna: "scaled as a whole so that its widest cisterna is as wide as the size above; the number of stacks and of cisternae, and the vesicles, are the picture's choice",
      capsule: "stretched so that it is as wide and as long as the size above; its folds and how it is cut open are the picture's choice",
      barrel: "stretched so that its barrel is as wide and as long as the size above; its nine rods' thickness, and that it lies on its side, are the picture's choice",
    }[model.sets];
    return `${model.words.charAt(0).toUpperCase()}${model.words.slice(1)}; built by the Cell view's own builders and ${sets}. An illustration, at the bench's one scale.${plank}`;
  }

  /** The plank an organelle stands on: "small" for the small organelles' own, else "shelf". */
  plankOf(id) {
    return this.ensureShelf()?.layout.items.find((item) => item.id === id)?.plank === "small" ? "small" : "shelf";
  }

  /** What is chosen on the bench, if anything: the bench itself as a stop, or an organelle on the shelf, leave the bench as it is. */
  benchChoice() {
    return this.selected && this.selected !== BENCH_ID && !organelleKind(this.selected) ? this.selected : null;
  }

  /** The bench as a stop of its own: what it holds, and how much smaller its machines are than the organelles above it. */
  describeBench() {
    const label = speciesLabel(this.model.raw, this.species);
    const range = this.benchRange();
    const largest = this.shelf?.layout.items.filter((item) => item.type === "shape").sort((a, b) => Math.max(b.w, b.h) - Math.max(a.w, a.h))[0];
    const facts = [["Its machines", `${this.counts.machines.toLocaleString("en-US")} machines, ${this.counts.sized.toLocaleString("en-US")} of them drawn to scale${range ? `, from ${lengthWords(range[0])} to ${lengthWords(range[1])} at their longest` : ""}`], ["Its scale", "One scale for every shape: the scale bar etched on the bench is 100 nm, as the shelf's organelles are drawn at the same scale."]];
    if (largest && range) facts.push(["Beside the shelf", `The ${largest.item.label.toLowerCase()} on the shelf is about ${Math.round((Math.max(largest.w, largest.h) * UNIT_NM) / range[1]).toLocaleString("en-US")} times as wide as the largest machine here.`]);
    return { id: BENCH_ID, label: "The bench", kind: "machines", eyebrow: `Machines · ${label}`, chips: [{ label: "Illustration", title: "Simple shapes at a size in hand, and cards: not structures" }], plain: `The machines of ${label}, in trays by what they do${this.organelles.length ? ", below the shelf of its organelles" : ""}.`, facts, sections: [], doors: [] };
  }

  /** The longest and shortest of the bench's shapes drawn to scale, at their longest, in nanometres; null where it has none. */
  benchRange() {
    const sizes = (this.layout?.items || []).filter((item) => item.type === "shape").map((item) => Math.max(item.w, item.h, item.d) * UNIT_NM);
    return sizes.length ? [Math.min(...sizes), Math.max(...sizes)] : null;
  }

  /**
   * The loupe's doors: on a machine drawn to scale, to hold it beside an organelle (the one last chosen, else the first on the
   * shelf with a size); on an organelle, to hold beside it the machine last chosen; and to put the loupe away where it is shown.
   */
  loupeDoors(id) {
    const doors = [];
    // Only beside an organelle on the shelf's plank: the lens lies on the shelf before it (the small organelles' plank stands just
    // behind the bench, with no room for a lens before it).
    const sized = this.organelles.some((item) => item.sized) ? this.organelles.filter((item) => item.sized && this.plankOf(item.id) === "shelf") : [];
    if (!sized.length) return doors;
    if (organelleKind(id)) {
      const machine = this.lastMachine && this.layout?.items.find((item) => item.id === this.lastMachine && item.type === "shape");
      if (machine && this.item(id)?.sized && !(this.loupe?.machine === machine.id && this.loupe?.organelle === id)) doors.push({ label: `Hold the ${machine.item.label} beside it, in a loupe`, lens: "machines", value: `loupe:${machine.id}@${id}` });
    } else if (this.layout?.items.some((item) => item.id === id && item.type === "shape")) {
      const organelle = sized.find((item) => item.id === this.lastOrganelle) || sized[0];
      if (!(this.loupe?.machine === id && this.loupe?.organelle === organelle.id)) doors.push({ label: `Hold it beside the ${organelle.label.toLowerCase()}, in a loupe`, lens: "machines", value: `loupe:${id}@${organelle.id}` });
    }
    // While a machine is held, the way back stands first: it ends the loupe and puts the machine back on the bench, still chosen.
    if (this.loupe && (this.loupe.machine === id || this.loupe.organelle === id)) return [{ label: "Put it back on the bench", lens: "machines", value: "loupe:off" }];
    return doors;
  }

  /**
   * Ends the loupe where the visitor goes (Escape, the panel closed, a stop of the rail, the bench's mark, anything else chosen):
   * the speck and the lens are taken away, and the camera goes where it was asked to, or stays.
   */
  endLoupe() {
    if (!this.loupe) return false;
    this.lastLoupe = this.loupe;
    this.loupe = null;
    this.buildLoupe();
    this.buildLabels();
    this.onOpen?.();
    return true;
  }

  /** "Put it back": the loupe ends, and the machine is chosen on the bench and travelled to. */
  putBack() {
    const held = this.loupe || this.lastLoupe;
    this.endLoupe();
    if (!held) return;
    this.stop = "bench";
    this.onShown?.(held.machine);
    this.focus(held.machine);
  }

  /** Escape: the loupe ends first, where the camera stands; otherwise the page's own Escape. */
  escape() {
    return this.endLoupe();
  }

  /** A machine held beside an organelle (`machine@organelle`), or the loupe put away (`off`): the camera travels to it. */
  holdLoupe(spec) {
    if (spec === "off") {
      this.putBack();
      return;
    }
    const [machine, organelle] = String(spec).split("@");
    if (!this.layout?.items.some((item) => item.id === machine && item.type === "shape") || !this.item(organelle)?.sized || this.plankOf(organelle) !== "shelf") return;
    this.loupe = { machine, organelle };
    this.lastMachine = machine;
    this.lastOrganelle = organelle;
    this.stop = "shelf";
    this.ensureShelf();
    this.buildLoupe();
    this.buildLabels();
    this.onShown?.(machine); // its panel: what the lens holds
    this.travelTo(this.organelleView(organelle));
    this.focused = { id: organelle, organelle: true, insets: JSON.stringify(this.stage.insets || {}), until: now() + 1600 };
  }

  /**
   * The loupe: the machine at its true size beside the organelle, a speck; a lens lying on the shelf beside it, its frame
   * marked, holding the same machine magnified by a round factor; a line from the speck to the lens; and the factor written
   * on the frame (buildLabels). Its shapes are the machine's outline, as on the bench.
   */
  buildLoupe() {
    if (this.loupeGroup) {
      this.loupeGroup.removeFromParent();
      disposeTree(this.loupeGroup);
      this.loupeGroup = this.loupeBox = this.loupeInfo = null;
    }
    const loupe = this.loupe, shelf = this.shelf;
    if (!loupe || !shelf) return;
    const at = shelf.layout.items.find((item) => item.id === loupe.organelle && item.type === "shape");
    const entry = this.layout?.items.find((item) => item.id === loupe.machine && item.type === "shape");
    if (!at || !entry) return;
    const longest = Math.max(entry.w, entry.h, entry.d);
    const radius = Math.min(260, Math.max(60, 0.16 * Math.max(at.w, at.h)));
    const most = (1.1 * radius) / longest, power = Math.pow(10, Math.floor(Math.log10(most)));
    const factor = [5, 2, 1].map((step) => step * power).find((value) => value <= most) ?? power;
    const front = shelf.layout.front;
    const speckAt = new THREE.Vector3(at.x - Math.min(at.w * 0.3, 260), 0, front + 70);
    const lensAt = new THREE.Vector3(speckAt.x + radius + 140, 0, front + radius + 60);
    const group = new THREE.Group();
    const material = (this.materials.loupeBody ??= new THREE.MeshStandardMaterial({ roughness: 0.38, metalness: 0.06, envMapIntensity: 1 }));
    const speck = this.machineBodies(entry, 1, material), big = this.machineBodies(entry, factor, material);
    speck.position.copy(speckAt);
    big.position.copy(lensAt);
    const frame = new THREE.Mesh(new THREE.TorusGeometry(radius, Math.max(2, radius * 0.03), 10, 96).rotateX(Math.PI / 2), (this.materials.loupeFrame ??= new THREE.MeshStandardMaterial({ roughness: 0.3, metalness: 0.4 })));
    frame.position.copy(lensAt).setY(Math.max(2, radius * 0.03));
    frame.userData.unpickable = true;
    const glass = new THREE.Mesh(new THREE.CircleGeometry(radius * 0.98, 72).rotateX(-Math.PI / 2), (this.materials.loupeGlass ??= new THREE.MeshStandardMaterial({ roughness: 0.15, metalness: 0, transparent: true, opacity: 0.16, depthWrite: false })));
    glass.position.copy(lensAt).setY(0.6);
    glass.userData.unpickable = true;
    const toward = lensAt.clone().sub(speckAt).setY(0).normalize();
    const leader = new THREE.Line(new THREE.BufferGeometry().setFromPoints([speckAt.clone().setY(entry.h * 0.5), lensAt.clone().addScaledVector(toward, -radius).setY(Math.max(2, radius * 0.03))]), (this.materials.loupeLine ??= new THREE.LineBasicMaterial({ transparent: true, opacity: 0.8 })));
    leader.userData.unpickable = true;
    group.add(speck, big, frame, glass, leader);
    shelf.root.add(group);
    this.loupeGroup = group;
    this.loupeInfo = { factor, speckAt, lensAt, radius, entry, organelle: at };
    this.loupeBox = new THREE.Box3().setFromPoints([speckAt, lensAt.clone().add(new THREE.Vector3(radius, longest * factor, radius)), lensAt.clone().add(new THREE.Vector3(-radius, 0, -radius))]);
    this.applyColours();
  }

  /** A machine's outline at `factor` times its true size, standing on its lowest point at the origin, chosen as the machine. */
  machineBodies(entry, factor, material) {
    const shape = entry.shape, group = new THREE.Group();
    if (shape.kind === "measured") {
      const inner = new THREE.Group();
      for (const body of bodiesAt(shape, 1)) {
        const mesh = new THREE.Mesh((this.loupeBall ??= new THREE.SphereGeometry(0.5, 20, 14)), material);
        const [a, b, c] = body.axes.map((axis) => new THREE.Vector3(...axis));
        mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(a, b, c));
        mesh.position.set(...body.centre_nm.map((n) => n / UNIT_NM));
        mesh.scale.set(...body.across_nm.map((n) => n / UNIT_NM));
        inner.add(mesh);
      }
      inner.position.copy(this.standOffset(shape));
      group.add(inner);
    } else if (shape.kind === "ellipsoid") {
      const mesh = new THREE.Mesh((this.loupeBall ??= new THREE.SphereGeometry(0.5, 20, 14)), material);
      mesh.scale.set(shape.w, shape.h, shape.d);
      mesh.position.y = shape.h / 2;
      group.add(mesh);
    } else if (shape.kind === "rod") {
      const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(shape.radius, Math.max(0.01, shape.length - 2 * shape.radius), 8, 20), material);
      mesh.rotation.z = Math.PI / 2;
      mesh.position.y = shape.radius;
      group.add(mesh);
    }
    group.scale.setScalar(factor);
    group.userData.pick = entry.id;
    return group;
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  sections() {
    return listSections(this.catalogue, this.species);
  }

  get pickRoots() {
    return [this.root];
  }

  speciesChoice() {
    const species = (this.model.raw.species || []).filter((item) => this.catalogue?.species.includes(item.id) || (this.model.raw.proteins?.atlases || []).some((atlas) => atlas.id === item.id));
    return species.length > 1 ? { options: species.map((item) => [item.id, item.label, item.organism]), active: this.species } : null;
  }

  chrome() {
    const counts = this.counts;
    const label = speciesLabel(this.model.raw, this.species);
    const structural = this.catalogue.raw.benches?.[this.species];
    const chosen = this.item(this.selected) || (this.partOf(this.selected) ? this.item(this.partOf(this.selected)) : null);
    const levels = chosen ? levelsOf(chosen) : null;
    const shown = MARKS.filter((mark) => mark.when(this));
    const found = this.query ? (this.catalogue?.of(this.species) || []).filter((item) => this.catalogue.passes(item, this.query)).length : 0;
    const count = { [SWATCH.sized]: counts.sized, [SWATCH.card]: counts.cards, [SWATCH.organelle]: this.organelles.length, "mach-found": found, [SWATCH.chosen]: this.layout?.items.some((item) => item.id === this.selected) ? 1 : 0 };
    const groups = (this.catalogue?.groups || []).filter((group) => this.catalogue.inGroup(this.species, group.id).length);
    return {
      card: {
        heading: "Machines",
        species: this.speciesChoice(),
        find: { label: "Find a machine", placeholder: structural?.structures ? "Name, PDB ID or protein" : "Find a machine or a gene", value: this.query },
        marks: groups.length > 1 ? { label: "Group", options: [["all", "All groups"], ...groups.map((group) => [group.id, group.label])], active: this.focusGroup || "all" } : null,
        modes: levels ? { label: "Detail", options: levels.map((level) => [String(level.id), level.label]), active: String(this.built?.get(chosen.id)?.level ?? this.level), oneRow: true } : null,
        // A species the catalogue holds no bench for (one with an atlas, shown for its units of the law inventory) says so first,
        // by rule; while its bench is read, and where it cannot be, the card says so; else whether any machine has a size in hand.
        notice: !this.catalogue.species.includes(this.species) ? `No bench of machines has been gathered for ${label} yet${counts.laws ? `: only the units of the law inventory that its atlas finds stand here${counts.sized ? "" : ", each a card"}` : ""}.` : this.catalogue.benchState(this.species)?.status === "failed" ? this.catalogue.benchState(this.species).words : this.catalogue.raw.benches?.[this.species] && !this.catalogue.hasBench(this.species) ? `Reading the machines of ${label}…` : counts.sized ? null : `No machine of ${label} has a size in hand: each is a card, not a shape.`,
        // A species whose dossier looks by family: how many machines its own records name, and how many are candidates by family.
        stats: structural?.structures ? [[structural.machines, "3D entries"], [structural.structures, "PDB records"]] : counts.family || counts.none ? [[counts.named, "named by its own records"], [counts.family, "candidates by family"], [counts.laws, "in the law inventory"]] : [[counts.machines, "machines"], [counts.sized, "drawn to scale"], [counts.laws, "in the law inventory"]],
        own: () => this.cardNoneFound(),
        text: structural?.structures ? `Choose an entry to inspect its measured surface and individual chains. Related experimental structures are listed on each card. RCSB archive search: ${structural.searched}.` : `Illustration: simple shapes at a size in hand (a paper's, a species file's, or the viewer's own measure from a structure), not structures, and cards where no size is in hand. No machine here is in the engine.${counts.laws ? " The membrane machines in the tray of moving ions are units of the law inventory; each panel says what the inventory states of its laws, and which of them an active model declares." : ""}${this.organelles.length ? ` Behind the bench, a shelf holds ${label}'s organelles at the same scale, the small ones on a plank of their own: each drawn with the Cell view's model of it where there is one, else with a simple model, an illustration, at a size its panel gives with its source (a measurement in one cell type, or a general figure); one with no size in hand is a card. The rail travels between them.` : ""}`,
        sources: [
          { name: "The species' files and their own proteins", holds: "which machines each species has, how many, and the proteins its data marks with each (tools/build_catalogue.py)", licence: "each source's own, named in each panel; the files are the project's own, MIT" },
          { name: "Sizes", holds: "from the species' files, each with its sources (the attachment organelle's length); from the flagellar motor's own file; and the viewer's own measures from entries of the Protein Data Bank (the ribosome), each naming its entry, its definition and its tool", licence: "each source's own, named in each panel; the Protein Data Bank's entries CC0 1.0" },
          { name: "The law inventory", holds: "its units that are protein assemblies, as the Protein atlas lists them; its leaks and permeabilities are not machines and are left out", licence: "the project's own, MIT" },
        ],
      },
      legend: {
        title: "What the marks stand for",
        items: [...shown.map((mark) => ({ id: mark.id, label: mark.label, description: mark.description, count: count[mark.id] ?? 0, swatch: mark.id })), ...groups.map((group) => ({ id: groupSwatch(group.id), label: group.label, description: group.plain, count: this.catalogue.inGroup(this.species, group.id).length, swatch: groupSwatch(group.id) }))],
        note: { swatch: "mach-room", text: MACHINES_NOTE },
      },
      stamp: "Illustration",
      // The rail (the page's own, as the Cell view's levels): the bench, the shelf and the powers of ten between them, and a mark for what is chosen.
      ...(this.organelles.length && this.layout ? { rail: this.railOf(), railTitle: "Scale", railActive: this.nearestStop(), railBesidePanel: true } : {}),
    };
  }

  /** What the page's scale bar says: one unit is ten nanometres, wherever the camera stands; the bar follows the camera from the bench to the shelf. */
  scaleInfo() {
    return this.organelles.length ? { micronsPerUnit: UNIT_NM / 1000 } : null;
  }

  /**
   * The card's list of what the species' dossier looked for by family and found no candidate for: under its own heading,
   * with the dossier's caveat, each with its reference machine; never on the bench. The card's search finds them here.
   */
  cardNoneFound() {
    const none = this.catalogue?.noneFound(this.species) || [];
    if (!none.length) return [];
    const scene = this.model.raw, labelOf = (id) => (scene.species || []).find((item) => item.id === id)?.label || id;
    const query = this.query.trim().toLowerCase();
    const rows = none.filter((row) => !query || [row.label, this.catalogue.kinds.get(row.id)?.plain, ...row.looked_for.map(([gene]) => gene)].filter(Boolean).join(" ").toLowerCase().includes(query));
    if (query && !rows.length) return [];
    return [
      h(
        "details",
        { class: "card-more mach-none-found", open: Boolean(query) || Boolean(this.noneOpen), ontoggle: (event) => (this.noneOpen = event.target.open) },
        h("summary", {}, `${NONE_FOUND} · ${rows.length}`),
        h("p", { class: "card-text" }, noneFoundNote(labelOf(this.species))),
        h(
          "ul",
          { class: "card-extra" },
          rows.map((row) => h("li", {}, h("button", { class: "link-button", type: "button", onclick: () => this.onShown?.(`${PREFIX}${row.id}`) }, row.label), `: ${labelOf(row.reference)}'s, ${row.looked_for.length} ${row.looked_for.length === 1 ? "part" : "parts"} looked for`))
        )
      ),
    ];
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    // A bench laid out before its machines were read (they came while another view was shown): laid out again with them.
    if (!this.layout || this.layoutBench !== Boolean(this.catalogue?.hasBench(this.species))) this.build();
    this.readBench();
    if (stage.sun) {
      stage.sun.castShadow = false;
      stage.sun.position.set(this.layout.bounds.maxX * 0.6, 120, 90);
      stage.sun.target?.position.set(0, 0, this.layout.bench.z);
    }
    stage.dress?.(MACHINES_LOOK);
    this.light();
    this.stopLook ??= stage.look?.onChange?.(() => this.active && this.light());
    if (!this.stopRestore && stage.canvas?.addEventListener) {
      // A lost context that comes back: the names are written again and sent again.
      const restored = () => {
        this.flatNames?.userData.repaint?.();
        stage.invalidate?.();
      };
      stage.canvas.addEventListener("webglcontextrestored", restored);
      this.stopRestore = () => stage.canvas.removeEventListener("webglcontextrestored", restored);
    }
    if (stage.rig) {
      stage.rig.limits = { minDistance: 2, maxDistance: this.organelles.length ? this.farthest() : 900, minPolar: 0.2, maxPolar: Math.PI / 2 - 0.05 };
      stage.rig.setView(this.homeView());
      this.homeHeld = { insets: JSON.stringify(stage.insets || {}), until: now() + 2500 };
    }
    this.afterBuild(false);
    this.band = null;
    this.afterMove();
  }

  light() {
    const { stage } = this;
    if (!stage.renderer || !stage.scene) return;
    const dark = stage.palette?.dark;
    const studio = stage.look?.on?.("reflections") ? (this.studio ??= makeStudio(stage.renderer)) : null;
    this.environment ??= makeEnvironment(stage.renderer);
    stage.scene.environment = studio || this.environment;
    stage.scene.environmentIntensity = dark ? 0.8 : 0.95;
    if (stage.sky) stage.sky.intensity = dark ? 0.9 : 1.3;
    if (stage.sun) stage.sun.intensity = dark ? 2 : 1.8;
  }

  deactivate() {
    const { stage } = this;
    this.active = false;
    this.travel = null;
    stage.dress?.({ rich: false });
    stage.scene.remove(this.root);
    if (stage.scene) stage.scene.environment = null;
    stage.applyPalette?.();
    this.labels.clear();
  }

  /**
   * The opening view, fitted to what the page's cards and panel leave of the screen: the shapes drawn to scale, with
   * room round them for their names, where the species has any (machines of 10 to 30 nm are seen, not the bench's
   * cards); the whole bench where it has none.
   */
  /** The view of the stop the view stands at: the bench's opening view, the shelf's, or a power of ten on the way between. */
  homeView() {
    if (this.stop === "shelf" && this.organelles.length) return this.shelfView() || this.benchView();
    if (this.stop === "small" && this.organelles.length) return this.stopViews().small || this.shelfView() || this.benchView();
    const power = /^nm(\d+)$/.exec(this.stop || "");
    if (power && this.layout) return this.pathView(this.distanceForBar(Number(power[1])));
    return this.layout ? this.benchView() : this.benchHome();
  }

  /** The bench's opening view. */
  benchHome() {
    const { bounds } = this.layout;
    const shapes = this.layout.items.filter((item) => item.type === "shape");
    const bench = new THREE.Box3(new THREE.Vector3(bounds.minX, 0, bounds.minZ), new THREE.Vector3(bounds.maxX, Math.min(bounds.maxY, 12), bounds.maxZ));
    if (!shapes.length) return this.fitOnScreen(bench, 0.04);
    const box = new THREE.Box3();
    for (const shape of shapes) {
      box.expandByPoint(new THREE.Vector3(shape.x - shape.w / 2, 0, shape.z - shape.d / 2));
      box.expandByPoint(new THREE.Vector3(shape.x + shape.w / 2, shape.y + shape.h, shape.z + shape.d / 2));
    }
    box.expandByVector(new THREE.Vector3(5, 0, 4));
    box.max.y += 2;
    // Where the shapes spread over most of the bench (the human's), the whole bench, so that no tray is cut at the edge.
    const spread = Math.max((box.max.x - box.min.x) / (bounds.maxX - bounds.minX), (box.max.z - box.min.z) / (bounds.maxZ - bounds.minZ));
    return spread >= 0.6 ? this.fitOnScreen(bench, 0.04) : this.fitOnScreen(box, 0.06);
  }

  fitOnScreen(box, margin) {
    const { stage } = this, { bottom = 0, left = 0 } = stage.insets || {};
    const width = stage.width || 1600, height = stage.height || 1000, fov = stage.camera?.fov || 34;
    // On a wide window the scale rail stands at the right of the picture (beside a panel too): what is framed keeps clear of it.
    // (With a panel open the rail folds behind the page's button beside it, and takes no room from the picture.)
    const rail = this.organelles?.length && width >= 761 && !stage.insets?.right ? 230 : 0;
    const right = (stage.insets?.right || 0) + rail;
    const seen = Math.max(0.2, (height - bottom) / height);
    const narrowed = (2 * Math.atan(Math.tan((fov * Math.PI) / 360) * seen) * 180) / Math.PI;
    const view = fitView(box, { fov: narrowed, aspect: Math.max(0.3, (width - right - left) / Math.max(1, height - bottom)), ...VIEW, margin });
    // The page centres the picture between its insets, where the rail is none: the target moves right by half the rail's width (in
    // the scene's units at its distance), so that what is framed stands in the middle of the room the rail leaves (20 November 2026:
    // the bench and the small organelles' plank stood under the rail at their stops).
    if (rail) view.target.addScaledVector(new THREE.Vector3(Math.cos(view.azimuth), 0, -Math.sin(view.azimuth)), ((rail / 2) * 2 * view.distance * Math.tan((fov * Math.PI) / 360)) / height);
    return view;
  }

  /** The direction across the screen at a view (its camera's right): a line along it stands level on the picture. */
  across(view) {
    return new THREE.Vector3(Math.cos(view.azimuth), 0, -Math.sin(view.azimuth));
  }

  /** Each shape drawn to scale has its name on the picture; a card's is written on it. The chosen machine's too. */
  buildLabels() {
    const labels = this.labels;
    if (!labels || !this.active) return;
    labels.clear();
    this.reserved = []; // the boxes the names of a stop take, as the stop shows them (nameRows, plankNames, benchMark)
    this.namesFor = this.screenKey(); // the screen they were laid out for: laid out again when it changes (update)
    this.namesView = this.viewKey(this.restingView()); // and the camera's view where it rests: laid out again where it comes to rest elsewhere
    // At the shelf's stop: the organelles' names, the small organelles' and the bench's marks, the loupe's words. At the small
    // organelles' stop: their names, the shelf's above them and the bench's mark. At the bench's: the bench's names as before, and
    // every organelle named above it. Each name of an organelle is a way to it.
    if (this.band === "shelf" && this.shelf) {
      this.shelfLabels(labels);
      return;
    }
    if (this.band === "small" && this.shelf?.layout.small) {
      this.smallLabels(labels);
      return;
    }
    this.shelfAbove(labels);
    for (const { entry } of this.shapeMeshes?.values() || []) {
      if (this.benchChoice() && entry.id !== this.selected) continue; // while one is chosen, only its name is on the picture
      labels.add({ id: entry.id, text: entry.item.label, anchor: new THREE.Vector3(entry.x, entry.y + entry.h + 0.6 + (this.lifts.get(entry.id) || 0), entry.z), priority: 700, kind: "part", lift: 2 });
    }
    const chosen = this.cardList?.find((entry) => entry.id === this.selected);
    if (chosen) labels.add({ id: chosen.id, text: chosen.item.label, anchor: new THREE.Vector3(chosen.x, chosen.y + LIFT + 0.8, chosen.z), priority: 2000, kind: "part", lift: 10 });
    // Where a chosen machine's membrane lies: its slab is named an illustration on the picture (a label with no click).
    const slab = this.built?.get(this.selected)?.group?.children.find((child) => child.userData.slab);
    if (slab) labels.add({ text: "Its membrane, where the ring stands (illustration)", anchor: slab.userData.anchor.clone().add(new THREE.Vector3(0, LIFT, 0)), priority: 1500, kind: "part", lift: 4 });
  }

  /** How many of the bench's 100 nm scale bars an organelle's size makes, in words, by what its size states. */
  barsWords(item) {
    const size = item.size;
    if (!size) return "a card: no size in hand";
    const middle = (values) => (values.length > 1 ? (values[0] + values[values.length - 1]) / 2 : values[0]);
    // Its size in its own unit first, then how many of the bench's own etched bars (100 nm, whatever the page's bar reads) it makes.
    const bars = (nm) => `${Number((nm / 100).toPrecision(3)).toLocaleString("en-US")} of the bench's bars`;
    const um = (value) => `${Number(value.toPrecision(3))} µm`;
    if (size.shape === "sphere" || size.shape === "lens") return `${um(middle(size.across_um))} across, ${bars(middle(size.across_um) * 1000)}`;
    if (size.shape === "capsule") return `${um(middle(size.across_um))} across and ${um(middle(size.long_um))} long, ${bars(middle(size.across_um) * 1000)} across`;
    if (size.shape === "stack") return `${um(middle(size.across_um))} across, ${bars(middle(size.across_um) * 1000)}`;
    if (size.shape === "sheet") return `a sheet ${Number(middle(size.thick_nm).toPrecision(3))} nm thick`;
    return "";
  }

  /** An organelle's size in a few words, for its name at a stop: its width, or its width and length, a cisterna's, or a sheet's. */
  sizeShort(item) {
    const size = item.size;
    if (!size) return "a card";
    const middle = (values) => (values.length > 1 ? (values[0] + values[values.length - 1]) / 2 : values[0]);
    const um = (value) => `${Number(value.toPrecision(3))} µm`;
    if (size.shape === "capsule") return `${Number(middle(size.across_um).toPrecision(3))} by ${um(middle(size.long_um))}`;
    if (size.shape === "stack") return `cisternae ${um(middle(size.across_um))}`;
    if (size.shape === "sheet") return `sheets ${Number(middle(size.thick_nm).toPrecision(3))} nm`;
    return um(middle(size.across_um));
  }

  /** The organelles in the order the shelf shows them: the shelf's plank first, then the small organelles' (the catalogue's order in each). */
  shelfOrder() {
    const plank = new Map((this.ensureShelf()?.layout.items || []).map((entry) => [entry.id, entry.plank]));
    return [...this.organelles.filter((item) => plank.get(item.id) !== "small"), ...this.organelles.filter((item) => plank.get(item.id) === "small")];
  }

  /** How many pixels apart two points of the scene stand at a stop's view (the page's camera: the insets shift the picture, never scale it). */
  pixelsAt(view, a, b) {
    return Math.abs(this.screenAt(view, b).x - this.screenAt(view, a).x);
  }

  /** Where a point of the scene stands on the screen at a stop's view, in pixels from the picture's middle (the page's camera). */
  screenAt(view, point) {
    // Where the camera rests at that view, the page's own projection (exactly where the label layer will put the point); on a
    // phone a camera of the page's measure alone put the small organelles' names a few pixels off, and two met (20 November 2026).
    if (view?.live && this.stage.project && this.stage.camera) {
      const { left = 0, right = 0, bottom = 0 } = this.stage.insets || {};
      const at = this.stage.project(point, point.clone());
      return { x: at.x - (this.stage.width || 1600) / 2 + (right - left) / 2, y: at.y - (this.stage.height || 1000) / 2 + bottom / 2 };
    }
    const camera = (this.measuring ??= new THREE.PerspectiveCamera(34, 1, 0.5, 1e7));
    camera.fov = this.stage.camera?.fov || 34;
    camera.aspect = (this.stage.width || 1600) / (this.stage.height || 1000);
    const sin = Math.sin(view.polar);
    camera.position.set(view.target.x + view.distance * sin * Math.sin(view.azimuth), view.target.y + view.distance * Math.cos(view.polar), view.target.z + view.distance * sin * Math.cos(view.azimuth));
    camera.lookAt(view.target);
    camera.updateMatrixWorld();
    camera.updateProjectionMatrix();
    const p = point.clone().project(camera);
    return { x: (p.x / 2) * (this.stage.width || 1600), y: (-p.y / 2) * (this.stage.height || 1000) };
  }

  /**
   * A name added to the picture and measured as the page draws it (the label layer measures each name it adds); where nothing
   * measures it (the tests' stand-in), its width estimated from its words. Returns the label and its box's width and height.
   */
  addName(labels, spec) {
    const label = labels.add(spec);
    const width = label?.width || spec.text.length * 7 + 14, height = label?.height || 18;
    // Its size and where a press goes, in its tooltip and for a reader of the screen (the name itself stays short).
    if (spec.title) {
      label?.element?.setAttribute?.("title", spec.title);
      label?.element?.setAttribute?.("aria-label", spec.title);
    }
    // The box the label layer gives it (3 px each side, 2 above and below), and a margin, so that names never meet.
    return { label, w: width + 12, h: height + 6 };
  }

  /**
   * The box a name takes on the screen, from its point (`at`, in pixels from the picture's middle), its width and height with their
   * margins, and its lift: moved along to stay inside the window, as the label layer moves a name near its edge (4 px), so that a
   * name at the edge is counted where it will stand (20 November 2026: on a phone the COPI vesicle's name, moved in from the right
   * edge, met the peroxisome's).
   */
  nameBox(at, w, h, lift) {
    const width = this.stage.width || 1600, { left = 0, right = 0 } = this.stage.insets || {}, shift = width / 2 - (right - left) / 2;
    const real = w - 12, middle = at.x + shift, edge = 4;
    const start = width > edge * 2 + real ? Math.max(edge, Math.min(middle - real / 2, width - edge - real)) : middle - real / 2;
    return { left: start - 6 - shift, right: start + real + 6 - shift, top: at.y - lift - h, bottom: at.y - lift };
  }

  /** Whether two boxes on the screen meet. */
  static meets(one, other) {
    return one.left < other.right && one.right > other.left && one.top < other.bottom && one.bottom > other.top;
  }

  /**
   * Names in rows across the picture, about a point of the scene (`centre`, as the stop's `view` shows it), `fill` pixels wide: each
   * row holds as many as fit across it, each anchored where its words have room, each row at the lift nearest its own where none of
   * its names meets another name of the stop, so that no name gives way to a neighbour. The rows run along the camera's own right,
   * so that at the stop they stand level. Each name is measured as the page draws it.
   */
  nameRows(labels, entries, centre, view, { lift = 6, priority = 720, fill = 600 } = {}) {
    const span = Math.max(60, fill);
    const made = entries.map((entry) => ({ entry, ...this.addName(labels, { id: entry.id, text: entry.text, title: entry.title, anchor: centre.clone(), priority, kind: "part", lift }) }));
    const step = Math.max(26, ...made.map((value) => value.h + 2));
    const rows = [];
    for (const value of made) {
      const row = rows.at(-1);
      if (!row || row.used + value.w > span) rows.push({ items: [value], used: value.w });
      else {
        row.items.push(value);
        row.used += value.w;
      }
    }
    // The top row stays below the page's bar (the label layer puts off a name whose top is above it, 56 px): where the rows would
    // reach above 62 px at the stop, their point moves toward the camera along the floor, lower on the picture, until they fit
    // (20 November 2026: on a 720 px window about 90 px stand between the bar and the bench's back edge).
    const height = this.stage.height || 1000, bottom = this.stage.insets?.bottom || 0;
    const screenY = (point) => height / 2 + this.screenAt(view, point).y - bottom / 2;
    const need = lift + (rows.length - 1) * step + step, toward = new THREE.Vector3(Math.sin(view.azimuth), 0, Math.cos(view.azimuth));
    let point = centre.clone();
    if (screenY(point) - need < 62) {
      let low = 0, high = view.distance * 0.5;
      for (let round = 0; round < 30; round++) {
        const middle = (low + high) / 2;
        if (screenY(centre.clone().addScaledVector(toward, middle)) - need < 62) low = middle;
        else high = middle;
      }
      point = centre.clone().addScaledVector(toward, high);
    }
    const way = this.across(view), perUnit = Math.max(1e-6, this.pixelsAt(view, point, point.clone().add(way)));
    const a = point.clone().addScaledVector(way, -span / 2 / perUnit), b = point.clone().addScaledVector(way, span / 2 / perUnit);
    // Each row at the lift nearest its own (upward first, then below) where none of its names meets a box another name of the stop
    // takes (the planks' names, the bench's mark, the rows before it), within the picture: below the bar, above the hint line.
    const reserved = (this.reserved ??= []);
    const inside = (box) => box.top >= 62 - height / 2 + bottom / 2 && box.bottom <= height / 2 - bottom / 2 - 40;
    rows.forEach((row, index) => {
      let at = Math.max(0, (span - row.used) / 2);
      const placed = row.items.map((value) => {
        const anchor = a.clone().lerp(b, Math.min(1, (at + value.w / 2) / span));
        at += value.w;
        return { ...value, anchor, screen: this.screenAt(view, anchor) };
      });
      const boxesAt = (rowLift) => placed.map(({ w, h, screen }) => this.nameBox(screen, w, h, rowLift));
      const tries = [0, 1, 2, 3, 4, 5, 6, 7, 8, -1, -2, -3, -4, -5, -6].map((k) => lift + (index + k) * step);
      const rowLift = tries.find((value) => boxesAt(value).every((box) => inside(box) && !reserved.some((other) => MachinesLens.meets(box, other)))) ?? lift + index * step;
      reserved.push(...boxesAt(rowLift));
      for (const { label, anchor } of placed) {
        if (!label) continue;
        label.anchor = anchor;
        label.lift = rowLift;
      }
    });
  }

  /** At the bench's stop: every organelle named above the bench's back edge, the shelf's first, each name a way up to it. */
  shelfAbove(labels) {
    const items = this.organelles, bounds = this.layout?.bounds;
    // While a machine is chosen only its name is on the picture, as the bench's own rule has it: the shelf's names wait.
    if (!items.length || !bounds || this.benchChoice()) return;
    // On a phone the bench's back edge stands under the bar: one name only, at the bench's front, within reach of a thumb,
    // the first organelle with how many more stand on the shelf.
    if ((this.stage.width || 1600) < 760) {
      const first = items[0];
      labels.add({ id: first.id, text: `↑ The shelf: ${first.label}, ${this.barsWords(first).split(",")[0]}${items.length > 1 ? `, and ${items.length - 1} more` : ""}`, anchor: new THREE.Vector3(0, 0, bounds.maxZ - 1), priority: 720, kind: "part", lift: 6 });
      return;
    }
    // Short names in level rows above the back edge, as many to a row as the picture's free width holds, each with its size in its
    // tooltip; one press on a name travels to its organelle (20 November 2026: a dozen long names, one a row, stood above the bar).
    const entries = this.shelfOrder().map((item) => ({ id: item.id, text: `↑ ${item.label}`, title: `${item.label}, ${this.sizeShort(item)}: travel up to it` }));
    this.nameRows(labels, entries, new THREE.Vector3((bounds.minX + bounds.maxX) / 2, 0, bounds.minZ - 10), this.viewFor(this.benchView()), { fill: 0.86 * this.freeWidth() });
  }

  /** The picture's free width in pixels: the screen less the cards and the panel beside it, and the rail on a wide window. */
  freeWidth() {
    const { left = 0, right = 0 } = this.stage.insets || {}, width = this.stage.width || 1600;
    return Math.max(120, width - left - right - (width >= 761 && !right ? 230 : 0));
  }

  /** The bench as a small marked tray, at the shelf's stop and the small organelles': a way down to it. */
  benchMark(labels, lift, view = null) {
    const range = this.benchRange(), bounds = this.layout.bounds;
    const text = `↓ The bench: ${this.counts.machines.toLocaleString("en-US")} machines${range ? `, ${lengthWords(range[0])} to ${lengthWords(range[1])}` : ""}`, anchor = new THREE.Vector3(0, 4, (bounds.minZ + bounds.maxZ) / 2);
    const { w, h } = this.addName(labels, { id: BENCH_ID, text, anchor, priority: 900, kind: "part", lift });
    if (view) {
      const at = this.screenAt(view, anchor);
      (this.reserved ??= []).push(this.nameBox(at, w, h, lift));
    }
  }

  /**
   * Each organelle of a plank named at its top, at the plank's stop: from left to right, each at the lowest lift where its box (as
   * the stop shows it, its width as the page draws it) meets no box before it, so that no name gives way to a neighbour.
   */
  plankNames(labels, plank, view) {
    const entries = this.shelf.layout.items.filter((entry) => entry.plank === plank).map((entry) => {
      const anchor = new THREE.Vector3(entry.x, entry.h + (plank === "small" ? 2 : 8), entry.z + (entry.type === "card" ? 0 : entry.d * 0.1));
      return { entry, anchor, at: view ? this.screenAt(view, anchor) : { x: entry.x, y: 0 }, ...this.addName(labels, { id: entry.id, text: entry.item.label, anchor, priority: 800, kind: "part", lift: 6 }) };
    }).sort((a, b) => a.at.x - b.at.x);
    const boxes = [];
    for (const { label, at, w, h } of entries) {
      let lift = 6;
      for (let row = 0; row < 8; row++, lift += h + 2) {
        const box = this.nameBox(at, w, h, lift);
        if (!boxes.some((other) => MachinesLens.meets(box, other))) {
          boxes.push(box);
          if (view) (this.reserved ??= []).push(box);
          break;
        }
      }
      if (label) label.lift = lift;
    }
  }

  /** At the small organelles' stop: each named on its plank, the shelf's named above them (a way up), and the bench's mark (a way down). */
  smallLabels(labels) {
    const small = this.shelf.layout.small, phone = (this.stage.width || 1600) < 760;
    this.plankNames(labels, "small", this.viewFor(this.stopViews().small));
    const large = this.shelfOrder().filter((item) => this.plankOf(item.id) === "shelf");
    // The shelf's names above the small organelles' plank, at its back edge and as high as its tallest, clear of their names.
    const b = small.bounds, top = new THREE.Vector3(0, b.maxY, b.minZ - 10);
    this.benchMark(labels, phone ? 6 : 44, this.viewFor(this.stopViews().small));
    // On a phone, one name (the first of the shelf's, with how many more), set where it meets no other name, as the rows are.
    if (phone && large.length) this.nameRows(labels, [{ id: large[0].id, text: `↑ The shelf: ${large[0].label}${large.length > 1 ? `, and ${large.length - 1} more` : ""}` }], top, this.viewFor(this.stopViews().small), { lift: 40, fill: 0.92 * this.freeWidth() });
    else if (large.length) this.nameRows(labels, large.map((item) => ({ id: item.id, text: `↑ ${item.label}`, title: `${item.label}, ${this.sizeShort(item)}: travel up to it on the shelf` })), top, this.viewFor(this.stopViews().small), { lift: 40, fill: 0.86 * this.freeWidth() });
  }

  /** At the shelf's stop: each organelle's name, the small organelles named before it (a way down to each), the bench's mark, and the loupe's words. */
  shelfLabels(labels) {
    const phone = (this.stage.width || 1600) < 760, layout = this.shelf.layout;
    this.plankNames(labels, "shelf", this.viewFor(this.shelfView()));
    this.benchMark(labels, phone ? 6 : 44, this.viewFor(this.shelfView())); // on a wide window lifted clear of the hint line at the picture's foot; on a phone low, where it would cover the small organelles above the bench
    const small = this.shelfOrder().filter((item) => this.plankOf(item.id) === "small");
    if (small.length) {
      // In the free strip before the shelf's organelles, across the shelf's width: on a phone one name, with how many more.
      const z = layout.front + SHELF.front * 0.35, b = layout.bounds;
      if (phone) this.nameRows(labels, [{ id: small[0].id, text: `↓ Small organelles: ${small[0].label}${small.length > 1 ? `, and ${small.length - 1} more` : ""}` }], new THREE.Vector3((b.minX + b.maxX) / 2, 0, z), this.viewFor(this.shelfView()), { priority: 760, fill: 0.92 * this.freeWidth() });
      else this.nameRows(labels, small.map((item) => ({ id: item.id, text: `↓ ${item.label}`, title: `${item.label}, ${this.sizeShort(item)}: travel to it on the small organelles' plank` })), new THREE.Vector3((b.minX + b.maxX) / 2, 0, z), this.viewFor(this.shelfView()), { priority: 760, fill: 0.86 * this.freeWidth() });
    }
    const info = this.loupeInfo;
    if (info && this.loupeGroup) {
      labels.add({ id: info.entry.id, text: `${info.entry.item.label}, at its true size`, anchor: info.speckAt.clone().setY(info.entry.h + 2), priority: 1200, kind: "part", lift: 10 });
      const lens = labels.add({ text: `In the loupe: magnified ${info.factor.toLocaleString("en-US")} times · Put it back ×`, anchor: info.lensAt.clone().add(new THREE.Vector3(0, 4, info.radius)), priority: 1300, kind: "part", lift: 4 });
      // The label is the loupe's own control: a press, Enter or Space puts the machine back on the bench.
      const element = lens?.element;
      if (element?.addEventListener) {
        element.setAttribute("role", "button");
        element.tabIndex = 0;
        element.setAttribute("aria-label", "Put it back on the bench: end the loupe");
        element.dataset.loupe = "off";
        element.addEventListener("click", () => this.putBack());
        element.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.putBack();
          }
        });
      }
    }
  }

  setSelection(id) {
    // Choosing anything but what the loupe holds, or letting go (the panel closed), ends the loupe.
    if (this.loupe && id !== this.loupe.machine && id !== this.loupe.organelle) this.endLoupe();
    // An organelle on the shelf, or the bench as a stop: chosen, and the camera travels to it (a press on its name, the List).
    if (id === BENCH_ID || organelleKind(id)) {
      const before = this.selected;
      this.selected = this.has(id) ? id : null;
      this.selectedPart = null;
      if (organelleKind(this.selected)) this.lastOrganelle = this.selected;
      const kindAt = (value) => this.shapeMeshes?.get(value)?.entry.shape.kind;
      if (before && before !== this.selected && ["machine", "measured"].includes(kindAt(before))) this.rebuildMachine(before);
      this.refresh();
      if (this.active && this.selected && before !== this.selected) this.focus(this.selected);
      this.onChrome?.();
      return;
    }
    const first = this.selected, levelBefore = this.built?.get(first)?.level;
    // A measured part named before its machine shows it: the machine is drawn at that part's level first.
    const asked = id && !this.partOf(id) ? this.measuredPart(id) : null;
    if (asked) {
      this.selected = asked.owner;
      this.level = asked.level;
      for (const value of [first, asked.owner].filter((value, index, all) => value && all.indexOf(value) === index)) this.rebuildMachine(value);
    }
    const owner = this.partOf(id);
    const next = id && this.has(id) ? id : null;
    const before = this.selected;
    this.selected = owner ? owner : next;
    this.selectedPart = owner ? id : null;
    // A machine with a file is drawn with its parts while it is chosen, as an outline again when it is let go.
    // A measured machine that stays chosen is not rebuilt for a part or chain chosen in it: only its light moves.
    const kindAt = (value) => this.shapeMeshes?.get(value)?.entry.shape.kind;
    const rebuild = [before, this.selected].filter((value, index, all) => value && all.indexOf(value) === index && (kindAt(value) === "machine" || (kindAt(value) === "measured" && before !== this.selected)));
    if (before === this.selected && kindAt(before) === "measured") this.shadeParts(before);
    if (before !== this.selected && !owner) {
      const levels = this.selected ? levelsOf(this.item(this.selected)) : null;
      this.level = this.item(this.selected)?.entry?.structures ? SHAPE_LEVEL : levels?.find((value) => value.id > 1)?.id ?? 2;
    }
    for (const value of rebuild) this.rebuildMachine(value);
    if (this.layout?.items.some((item) => item.id === this.selected && item.type === "shape")) this.lastMachine = this.selected;
    this.refresh();
    // The card's Detail is offered while a machine with levels is chosen, and follows its level where a choice changed it
    // (a chain named by an address while a shape of parts is shown: the machine goes to its Subunits).
    if (first !== this.selected || this.built?.get(this.selected)?.level !== levelBefore) this.onChrome?.();
  }

  rebuildMachine(id) {
    const shown = this.shapeMeshes?.get(id);
    if (!shown) return;
    this.built.get(id)?.surface?.dispose();
    for (const child of [...shown.holder.children]) {
      shown.holder.remove(child);
      disposeTree(child);
    }
    this.built.delete(id);
    if (shown.entry.shape.kind === "measured") {
      this.buildMeasuredAt(shown.entry, shown.holder);
      this.placeOutlines();
    } else this.buildMachineAt(shown.entry, shown.holder);
  }

  setHover() {}

  /**
   * The legend's rows (the page's isolate): a group's row frames that group's tray, as the card's Group does; the organelles' row
   * travels to the shelf. Asked for on 20 November 2026 ("Making ATP" should zoom in to the right level).
   */
  setIsolate(id) {
    if (!this.active || !id) return;
    if (id === SWATCH.organelle && this.organelles.length) this.goToScale("shelf");
    const group = /^mach-g-(.+)$/.exec(id)?.[1];
    if (group) this.setMark(group);
  }

  /** The card's Detail: the level a chosen machine with a closer view is drawn at. */
  setMode(value) {
    const level = Number(value);
    // Any level the chosen machine offers (its file's, or its measure's: no fixed number of them).
    const offered = this.selected ? levelsOf(this.item(this.selected))?.map((value) => value.id) : null;
    if (!Number.isInteger(level) || level < 1 || (offered ? !offered.includes(level) : level > 3) || level === this.level) return;
    this.level = level;
    if (this.selected) this.rebuildMachine(this.selected);
    this.refresh();
    this.onChrome?.();
    this.onOpen?.();
  }

  /** The card's Group: the camera goes to that tray, and back to the whole bench when it is let go. */
  setMark(value) {
    this.focusGroup = value && value !== "all" ? value : null;
    this.onChrome?.();
    if (!this.active) return;
    // Framed on the bench, from wherever the camera stands (from the shelf it travels down, each power of ten in the same time).
    this.endLoupe();
    this.stop = "bench";
    const tray = this.layout.trays.find((item) => item.group === this.focusGroup);
    if (tray) this.flyToBox(new THREE.Box3(new THREE.Vector3(tray.x - tray.w / 2, 0, tray.z - tray.d / 2), new THREE.Vector3(tray.x + tray.w / 2, 4, tray.z + tray.d / 2)));
    else if (this.organelles.length) this.travelTo(this.benchView());
    else this.stage.rig?.flyTo?.(this.homeView(), 900);
  }

  /** A door from another view (the viewer's openDoor, `value`): the machine it names is chosen. */
  setFinding(id) {
    // The loupe's doors (loupeDoors): a machine held beside an organelle, or the loupe put away.
    if (typeof id === "string" && id.startsWith("loupe:")) {
      this.holdLoupe(id.slice("loupe:".length));
      return;
    }
    if (!id || !this.has(id)) return;
    this.onShown?.(id);
    // The camera goes to it, as to a choice an address names. A door opens this view afresh, even from its own panels
    // ("Back to the machine", "Its part"), and the view opens on the whole bench: with no flight it stayed there, and on
    // a phone the machine could lie under the card or the bar.
    if (this.active && this.selected) this.focus(id);
  }

  back() {
    return false;
  }

  setQuery(text) {
    const before = Boolean(this.query);
    this.query = String(text || "");
    this.refresh();
    if (before !== Boolean(this.query)) this.onChrome?.();
  }

  /** Colours, lifts and fades: what is chosen and what a search finds. */
  refresh() {
    if (!this.layout) return;
    const passes = (item) => !this.query || this.catalogue.passes(item, this.query);
    for (const entry of this.layout.items) this.liftTarget(entry.id, entry.id === this.selected ? LIFT : 0);
    this.applyColours(passes);
    if (this.active) this.buildLabels();
    this.stage.invalidate?.();
  }

  liftTarget(id, value) {
    (this.targets ??= new Map()).set(id, value);
  }

  applyColours(passes = () => true) {
    const palette = this.stage.palette || {};
    const tone = (value, fallback = "#888888") => new THREE.Color(value || fallback);
    const faint = (colour) => colour.clone().lerp(tone(palette.bg, "#ffffff"), 0.72);
    for (const [group, material] of this.materials.groups) material.color.copy(tone(palette[GROUP_HUE[group]] || palette.ghost));
    this.materials.card.color.set(0xffffff);
    this.materials.tab.color.set(0xffffff);
    // The trays' back rims, each in its group's colour.
    if (this.trayMeshes?.[1]) {
      this.materials.rim.color.set(0xffffff);
      this.trayBacks.forEach((back, index) => this.trayMeshes[1].setColorAt(index, tone(palette[GROUP_HUE[back.group]] || palette.ghost)));
      this.trayMeshes[1].instanceColor.needsUpdate = true;
    }
    // While a machine is chosen, every other one is faint, and so are the names written on the bench: the chosen one
    // is seen close, with nothing larger than it in letters behind it.
    const quiet = (id) => Boolean(this.benchChoice()) && id !== this.selected;
    if (this.flatNames) {
      this.flatNames.material.transparent = true;
      this.flatNames.material.opacity = this.benchChoice() ? 0.12 : 1;
    }
    // The bench's outlines: each machine's bodies in its group's colour, faint where a search does not find it.
    if (this.outlines) {
      this.materials.outline.color.set(0xffffff);
      this.outlineItems.forEach((item, index) => {
        const colour = tone(palette[GROUP_HUE[item.group]] || palette.ghost);
        this.outlines.setColorAt(index, passes(item.entry.item) && !quiet(item.id) ? colour : faint(colour));
      });
      if (this.outlines.instanceColor) this.outlines.instanceColor.needsUpdate = true;
    }
    if (this.cardList) {
      this.cardList.forEach((entry, index) => {
        const chosen = entry.id === this.selected, found = passes(entry.item) && !quiet(entry.id);
        const body = chosen ? tone(palette.accent) : tone(palette.dark ? palette.plateEdge : palette.plate, "#f4f7f9");
        const tab = chosen ? tone(palette.accent) : tone(palette[GROUP_HUE[entry.group]] || palette.ghost);
        this.cardBody.setColorAt(index, found ? body : faint(body));
        this.cardTab.setColorAt(index, found ? tab : faint(tab));
      });
      if (this.cardBody.instanceColor) this.cardBody.instanceColor.needsUpdate = true;
      if (this.cardTab.instanceColor) this.cardTab.instanceColor.needsUpdate = true;
    }
    for (const { entry, holder } of this.shapeMeshes?.values() || []) {
      // A machine drawn from its file, or a measured one shown with its parts, keeps its own materials (its parts' shades).
      const own = entry.shape.kind === "machine" || entry.shape.kind === "measured";
      const chosen = entry.id === this.selected && !own, found = passes(entry.item) && !quiet(entry.id);
      holder.traverse((object) => {
        if (!object.isMesh) return;
        if (!own) object.material = chosen ? this.materials.lit : this.groupMaterial(entry.group);
        // Faint where not found or not chosen; back to its own opacity (a see-through part's, the membrane's) otherwise.
        const material = object.material, rest = (material.userData.rest ??= { opacity: material.opacity, transparent: material.transparent });
        material.opacity = found ? rest.opacity : Math.min(rest.opacity, 0.25);
        material.transparent = rest.transparent || material.opacity < 1;
      });
    }
    if (palette.accent) this.materials.lit.emissive.set(palette.accent);
    this.materials.tray.color.copy(tone(palette.dark ? palette.plate : palette.plateEdge, "#dfe6eb"));
    this.materials.bench.color.copy(tone(palette.dark ? palette.bg : palette.plate, "#eef2f5"));
    this.materials.scale.color.copy(tone(palette.fg, "#12283a"));
    // A shelf's card: the organelle's own colour of the Cell view, light, so that it stands out on the shelf and reads as no shape.
    for (const material of this.shelfCards || []) material.color.copy(tone(palette[material.userData.hue] || palette.ghost)).lerp(tone(palette.bg, "#ffffff"), 0.45);
    if (this.loupeInfo) this.materials.loupeBody.color.copy(tone(palette[GROUP_HUE[this.loupeInfo.entry.group]] || palette.ghost));
    this.materials.loupeFrame?.color.copy(tone(palette.fg, "#12283a"));
    this.materials.loupeGlass?.color.copy(tone(palette.accent, "#1f6fd0"));
    this.materials.loupeLine?.color.copy(tone(palette.fg, "#12283a"));
  }

  /** A move toward what was chosen: its shape or card with its neighbours in the tray. */
  focus(id) {
    // The bench as a stop, and an organelle on the shelf: the camera travels there.
    if (id === BENCH_ID) {
      this.goToScale("bench");
      this.focused = { id, stop: true, insets: JSON.stringify(this.stage.insets || {}), until: now() + 1600 };
      return;
    }
    if (organelleKind(id)) {
      if (!this.item(id)) {
        this.focused = { id, box: null };
        return;
      }
      this.stop = this.plankOf(id);
      this.travelTo(this.organelleView(id));
      this.focused = { id, organelle: true, insets: JSON.stringify(this.stage.insets || {}), until: now() + 1600 };
      return;
    }
    const owner = this.partOf(id) || this.measuredPart(id)?.owner || id;
    const entry = this.layout?.items.find((item) => item.id === owner);
    // Not on the bench yet (its species' machines are being read): the camera is sent to it once they are laid out.
    if (!entry) {
      this.focused = { id, box: null };
      return;
    }
    this.stop = "bench";
    this.flyToBox(this.focusBox(entry), id);
  }

  /** The box a move toward a machine frames: its shape or card with its neighbours in the tray. */
  focusBox(entry) {
    if (entry.item.entry?.structures) {
      const centre = new THREE.Vector3(entry.x, entry.y + LIFT + entry.h / 2, entry.z);
      const room = new THREE.Vector3(entry.w, entry.h, entry.d).multiplyScalar(1.6);
      return new THREE.Box3().setFromCenterAndSize(centre, room);
    }
    const pad = entry.type === "card" ? 6 : Math.max(2, Math.max(entry.w, entry.h) * 0.6);
    return new THREE.Box3(new THREE.Vector3(entry.x - entry.w / 2 - pad, entry.y, entry.z - entry.d / 2 - pad), new THREE.Vector3(entry.x + entry.w / 2 + pad, entry.y + entry.h + LIFT + 1, entry.z + entry.d / 2 + pad));
  }

  flyToBox(box, id = null) {
    const { stage } = this, rig = stage.rig;
    if (!rig?.flyTo || box.isEmpty()) return;
    this.homeHeld = null;
    const view = this.fitOnScreen(box, 0.1);
    // A move to or from the shelf's side (the shelf down to a machine) is a travel, its time the same for each power of ten; a move
    // on the bench is a flight of a second, as it always was (the bench's checks press what it flies to once it has arrived).
    const shelfward = this.organelles.length > 0 && Math.max(view.distance, rig.distance) > 1.6 * this.benchView().distance;
    if (shelfward) this.travelTo(view);
    else {
      this.travel = null;
      rig.flyTo(view, 1000);
    }
    this.focused = { id, box: box.clone(), insets: JSON.stringify(stage.insets || {}), until: now() + 1600 };
  }

  /** The camera's view where it rests (no travel, no flight, no spin), else null. */
  restingView() {
    const rig = this.stage.rig, spin = rig?.velocity;
    if (this.travel || rig?.flight || !rig?.view || (spin && Math.abs(spin.azimuth) + Math.abs(spin.polar) > 1e-5)) return null;
    return rig.view();
  }

  /**
   * The view a stop's names are laid out for: the camera's own where it rests (a panel opened and closed, a choice framed, the
   * visitor's own turn or zoom), else the stop's (while the camera travels to it). 20 November 2026: names laid out for the stop's
   * view met where the camera rested a little farther out after the bench's panel closed.
   */
  viewFor(view) {
    const resting = this.restingView();
    return resting ? { ...resting, live: true } : view;
  }

  /** A view in a few numbers, to tell whether the camera rests where the names were laid out for. */
  viewKey(view) {
    return view ? [Math.round(Math.log(view.distance) * 100), Math.round(view.target.x), Math.round(view.target.y), Math.round(view.target.z), Math.round(view.azimuth * 100), Math.round(view.polar * 100)].join(",") : "";
  }

  /** The screen the stops' views and names are laid out for: its size and the room the page's cards and panel leave. */
  screenKey() {
    return `${JSON.stringify(this.stage.insets || {})}|${this.stage.width}x${this.stage.height}`;
  }

  update(dt = 16) {
    // The names are laid out in pixels for the screen as it was: a new size, or cards and a panel that settle after they were laid
    // out (a first visit), lays them out again.
    if (this.active && this.organelles.length && this.namesFor && this.namesFor !== this.screenKey()) this.buildLabels();
    // Where the camera comes to rest elsewhere than the names were laid out for (a quarter of a second at rest), they are laid out again.
    const resting = this.active && this.organelles.length ? this.viewKey(this.restingView()) : "";
    if (resting !== this.restingKey) this.restingSince = now();
    this.restingKey = resting;
    // The page draws only when something moves: until they are laid out again, the view asks for frames (20 November 2026: on a first
    // visit the camera was re-aimed as the cards settled, after the names were laid out, and no frame came to lay them out again).
    let waiting = false;
    if (resting && this.namesFor && resting !== this.namesView) {
      if (now() - this.restingSince > 250) {
        this.buildLabels();
        this.stage.invalidate?.();
      } else waiting = true;
    }
    if (this.stage.width && this.stage.height && columnsFor(this.stage) !== this.columns) {
      this.columns = columnsFor(this.stage);
      this.build();
      this.afterBuild(true);
      this.reaim();
      return true;
    }
    if (this.relayout) {
      this.relayout = false;
      this.build();
      this.afterBuild(!this.selected);
      this.reaim();
      return true;
    }
    const held = this.homeHeld, insets = JSON.stringify(this.stage.insets || {});
    if (held && !this.selected && now() < held.until && held.insets !== insets) {
      held.insets = insets;
      this.stage.rig?.setView?.(this.homeView());
    }
    const focused = this.focused;
    if (focused?.box && now() < focused.until && focused.insets !== insets) this.flyToBox(focused.box, focused.id);
    // An organelle travelled to: framed again in what a panel that opened meanwhile leaves of the picture.
    if ((focused?.organelle || focused?.stop) && now() < focused.until && focused.insets !== insets) {
      focused.insets = insets;
      this.travelTo(focused.stop ? this.homeView() : this.organelleView(focused.id));
    }
    const travelling = this.stepTravel(dt);
    if (travelling || Math.abs((this.stage.rig?.distance ?? 0) - (this.lastDistance ?? 0)) > 1e-6 * (this.lastDistance || 1)) this.afterMove();
    // The chosen machine rises; the others settle.
    const k = this.stage.reducedMotion ? 1 : Math.min(1, (dt / 1000) * 9);
    let moving = false, cards = false;
    for (const [id, target] of this.targets || []) {
      const at = this.lifts.get(id) || 0;
      if (Math.abs(target - at) < 1e-3) {
        if (at !== target) this.lifts.set(id, target);
        else continue;
      } else {
        this.lifts.set(id, at + (target - at) * k);
        moving = true;
      }
      const shape = this.shapeMeshes?.get(id);
      if (shape) shape.holder.position.y = shape.entry.y + this.lifts.get(id);
      else cards = true;
    }
    if (cards) this.placeCards();
    return moving || travelling || waiting;
  }

  applyPalette(palette) {
    this.palette = palette;
    if (!this.layout) return;
    this.applyColours((item) => !this.query || this.catalogue.passes(item, this.query));
    for (const [id, { group }] of this.built || []) {
      if (group) this.paint(group);
      this.shadeParts(id);
    }
    for (const { model } of this.shelf?.holders.values() || []) if (model) paintModel(model, palette);
    if (this.active) this.writeNames();
  }

  /** What one frame costs to draw, counted from the scene: draws and triangles of every visible thing. */
  cost() {
    let draws = 0, triangles = 0;
    this.root.traverseVisible((object) => {
      if (!(object.isMesh || object.isLine || object.isPoints)) return;
      const instances = object.isInstancedMesh ? object.count : 1;
      if (instances === 0) return;
      draws += 1;
      const geometry = object.geometry;
      if (object.isMesh) triangles += ((geometry.index ? geometry.index.count : geometry.attributes.position.count) / 3) * instances;
    });
    return { draws, triangles: Math.round(triangles) };
  }

  dispose() {
    this.dropShelf();
    this.stopLook?.();
    this.stopRestore?.();
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
