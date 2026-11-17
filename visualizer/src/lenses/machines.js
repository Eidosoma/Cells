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
import { IONS, PREFIX, kindOf } from "./machines_data.js";
import { catalogueOf, describe as describeItem, describePart, sections as listSections, levelsOf, SWATCH, groupSwatch } from "./machines_card.js";
import { layoutOf, bodiesAt, membraneOf, partOfChain, CARD, TRAY, BENCH, UNIT_NM } from "./machines_layout.js";

/** The look this view asks of the stage (core/look.js), as the Laws library's: natural colours under filmic light. */
export const MACHINES_LOOK = { rich: true, filmic: true, exposure: 1.04, contact: true, reach: 0.5, shade: 0.55 };
/** Each group's colour: a token of the page's palette (page.css), one for each thing the machines do. */
// Each group's own colour, told apart in both themes: the three groups the dossiers brought take colours no other tray has.
export const GROUP_HUE = { proteins: "bioRibosome", genes: "bioNucleus", dna: "bioChloroplast", atp: "bioFuel", ions: "bioIon", membranes: "bioEr", folding: "bioProtein", breaking: "bioSignal", moving: "bioMito", traffic: "bioWound" };
/** What each role of a machine file's part wears (as its closer view, machine_view.js, dresses it). */
const ROLE_HUE = { membrane: ["bioMembrane", 0.32, true], wall: ["ghost", 0.36, true], rotor: ["bioProtein", 1], stator: ["bioMito", 1], bearing: ["edge", 1], export: ["bioIon", 1], mark: ["fg", 1], swept: ["fg", 0.3, true], arrow: ["fg", 1] };
const VIEW = { azimuth: 0.12, polar: 0.98 };
const LIFT = 0.7; // how far a chosen machine rises from its tray
const MACHINE_SCALE = 1000 / UNIT_NM; // a machine file is drawn in micrometres; here one unit is ten nanometres
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
const columnsFor = (stage) => (stage.width && stage.height && stage.width < stage.height * 0.9 ? 1 : 3);

/** What each visual difference stands for: the legend's words. `when` says when a mark is drawn at all. */
export const MARKS = [
  { id: SWATCH.sized, label: "A shape: drawn to scale from a size in hand", description: "A simple shape at a size in hand, every one at the same scale (the scale bar on the bench is 100 nm): a size a paper or a species' file gives, or the viewer's own measure from a structure of the Protein Data Bank. Shapes, not structures.", when: (lens) => lens.counts.sized > 0 },
  { id: SWATCH.card, label: "A card: no size in hand, not to scale", description: "A machine whose size no source in hand gives: a card with its name, the same size for all. It is a label, not a shape.", when: (lens) => lens.counts.cards > 0 },
  { id: "mach-found", label: "Forward: found; faint: not found", description: "While a search is set, the machines it finds stand as they are and the rest fade.", when: (lens) => Boolean(lens.query) },
  { id: SWATCH.chosen, label: "Blue light: your choice", description: "The machine you chose rises from its tray and is lit.", when: () => true },
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
    if (this.selected && !this.has(this.selected)) this.selected = null;
    this.build();
    if (this.active) this.afterBuild(true);
    this.onChrome?.();
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
    this.applyColours();
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
    const level = this.level;
    const group = new THREE.Group(), ids = new Set();
    const ball = (this.ballGeometry ??= new THREE.SphereGeometry(0.5, 24, 16));
    // A chain wears the hue of the named part that holds it (by its entity or by its chain), where the overlay gives that part one.
    const partOf = (body) => (body.entity || body.chain || String(body.id || "").startsWith("chain-") ? partOfChain(shape, body) : null);
    const bodies = bodiesAt(shape, level).map((body) => ({ ...body, hue: body.hue || partOf(body)?.hue || null }));
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
    this.built.set(entry.id, { level, ids, group, bodies: mesh, measured: true });
    this.shadeParts(entry.id);
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
    mesh.material.color.set(0xffffff);
    mesh.userData.bodies.forEach((look, index) => {
      const base = new THREE.Color(palette[look.hue] || palette[GROUP_HUE[group]] || palette.ghost || "#888888");
      mesh.setColorAt(index, base.lerp(ground, (look.hue ? 0.3 : 0.45) * Math.min(1, look.shade)));
    });
    mesh.instanceColor.needsUpdate = true;
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
      plaques.push({ text, x: entry.x + 0.55, y: -entry.z, z: entry.y + entry.h + 0.02, h: fit(text, entry.w - 1.6, 1.15), align: "center", tone: "strong" });
    }
    // Each tray's name in its strip along the front, in one line or two.
    for (const tray of this.layout.trays) {
      tray.lines.forEach((line, index) => {
        const top = tray.z + tray.d / 2 - tray.head + 0.4 + TRAY.name * 0.5;
        plaques.push({ text: line, x: tray.x - tray.w / 2 + 0.9, y: -(top + index * TRAY.name * 1.25), z: 0.32, h: TRAY.name, align: "left", tone: "strong" });
      });
    }
    if (this.layout.scale) plaques.push({ text: `${this.layout.scale.nm} nm`, x: this.layout.scale.x + this.layout.scale.length + 0.8, y: -this.layout.scale.z, z: 0.02, h: 1.1, align: "left", tone: "soft" });
    this.flatNames = plaqueMesh(plaques, palette);
    if (this.flatNames) {
      this.flatNames.rotation.x = -Math.PI / 2;
      this.flatNames.material.transparent = true;
      this.flatNames.material.opacity = this.selected ? 0.12 : 1;
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
    if (this.item(id) || this.partOf(id) || this.measuredPart(id)) return true;
    const kind = kindOf(id);
    return Boolean(this.catalogue && (kind ? id === `${PREFIX}${kind}` && this.catalogue.kinds.has(kind) : this.catalogue.speciesWith(id).length));
  }

  describe(id) {
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
    return describeItem(this.catalogue, this.species, id, { scene: this.model.raw, level: this.built?.get(id)?.level ?? null });
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
    const label = (this.model.raw.species || []).find((item) => item.id === this.species)?.label || this.species;
    const chosen = this.item(this.selected) || (this.partOf(this.selected) ? this.item(this.partOf(this.selected)) : null);
    const levels = chosen ? levelsOf(chosen) : null;
    const shown = MARKS.filter((mark) => mark.when(this));
    const found = this.query ? (this.catalogue?.of(this.species) || []).filter((item) => this.catalogue.passes(item, this.query)).length : 0;
    const count = { [SWATCH.sized]: counts.sized, [SWATCH.card]: counts.cards, "mach-found": found, [SWATCH.chosen]: this.layout?.items.some((item) => item.id === this.selected) ? 1 : 0 };
    const groups = (this.catalogue?.groups || []).filter((group) => this.catalogue.inGroup(this.species, group.id).length);
    return {
      card: {
        heading: "Machines",
        species: this.speciesChoice(),
        find: { label: "Find a machine", placeholder: "Find a machine or a gene", value: this.query },
        marks: groups.length > 1 ? { label: "Group", options: [["all", "All groups"], ...groups.map((group) => [group.id, group.label])], active: this.focusGroup || "all" } : null,
        modes: levels ? { label: "Detail", options: levels.map((level) => [String(level.id), level.label]), active: String(this.built?.get(chosen.id)?.level ?? this.level) } : null,
        notice: counts.sized ? null : `No machine of ${label} has a size in hand: each is a card, not a shape.`,
        stats: [[counts.machines, "machines"], [counts.sized, "drawn to scale"], [counts.laws, "in the law inventory"]],
        text: `Illustration: simple shapes at a size in hand (a paper's, a species file's, or the viewer's own measure from a structure), not structures, and cards where no size is in hand. No machine here is in the engine. The membrane machines in the last tray are units of the law inventory; each panel says what the inventory states of its laws, and which of them an active model declares.`,
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
    };
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    if (!this.layout) this.build();
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
      stage.rig.limits = { minDistance: 2, maxDistance: 900, minPolar: 0.2, maxPolar: Math.PI / 2 - 0.05 };
      stage.rig.setView(this.homeView());
      this.homeHeld = { insets: JSON.stringify(stage.insets || {}), until: now() + 2500 };
    }
    this.afterBuild(false);
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
  homeView() {
    const { bounds } = this.layout;
    const shapes = this.layout.items.filter((item) => item.type === "shape");
    if (!shapes.length) {
      const box = new THREE.Box3(new THREE.Vector3(bounds.minX, 0, bounds.minZ), new THREE.Vector3(bounds.maxX, Math.min(bounds.maxY, 12), bounds.maxZ));
      return this.fitOnScreen(box, 0.04);
    }
    const box = new THREE.Box3();
    for (const shape of shapes) {
      box.expandByPoint(new THREE.Vector3(shape.x - shape.w / 2, 0, shape.z - shape.d / 2));
      box.expandByPoint(new THREE.Vector3(shape.x + shape.w / 2, shape.y + shape.h, shape.z + shape.d / 2));
    }
    box.expandByVector(new THREE.Vector3(5, 0, 4));
    box.max.y += 2;
    return this.fitOnScreen(box, 0.06);
  }

  fitOnScreen(box, margin) {
    const { stage } = this, { right = 0, bottom = 0, left = 0 } = stage.insets || {};
    const width = stage.width || 1600, height = stage.height || 1000, fov = stage.camera?.fov || 34;
    const seen = Math.max(0.2, (height - bottom) / height);
    const narrowed = (2 * Math.atan(Math.tan((fov * Math.PI) / 360) * seen) * 180) / Math.PI;
    return fitView(box, { fov: narrowed, aspect: Math.max(0.3, (width - right - left) / Math.max(1, height - bottom)), ...VIEW, margin });
  }

  /** Each shape drawn to scale has its name on the picture; a card's is written on it. The chosen machine's too. */
  buildLabels() {
    const labels = this.labels;
    if (!labels || !this.active) return;
    labels.clear();
    for (const { entry } of this.shapeMeshes?.values() || []) {
      if (this.selected && entry.id !== this.selected) continue; // while one is chosen, only its name is on the picture
      labels.add({ id: entry.id, text: entry.item.label, anchor: new THREE.Vector3(entry.x, entry.y + entry.h + 0.6 + (this.lifts.get(entry.id) || 0), entry.z), priority: 700, kind: "part", lift: 2 });
    }
    const chosen = this.cardList?.find((entry) => entry.id === this.selected);
    if (chosen) labels.add({ id: chosen.id, text: chosen.item.label, anchor: new THREE.Vector3(chosen.x, chosen.y + LIFT + 0.8, chosen.z), priority: 2000, kind: "part", lift: 10 });
    // Where a chosen machine's membrane lies: its slab is named an illustration on the picture (a label with no click).
    const slab = this.built?.get(this.selected)?.group?.children.find((child) => child.userData.slab);
    if (slab) labels.add({ text: "Its membrane, where the ring stands (illustration)", anchor: slab.userData.anchor.clone().add(new THREE.Vector3(0, LIFT, 0)), priority: 1500, kind: "part", lift: 4 });
  }

  setSelection(id) {
    const first = this.selected;
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
    const rebuild = [before, this.selected].filter((value, index, all) => value && all.indexOf(value) === index && ["machine", "measured"].includes(this.shapeMeshes?.get(value)?.entry.shape.kind));
    if (before !== this.selected && !owner) {
      const levels = this.selected ? levelsOf(this.item(this.selected)) : null;
      this.level = levels?.find((value) => value.id > 1)?.id ?? 2;
    }
    for (const value of rebuild) this.rebuildMachine(value);
    this.refresh();
    if (first !== this.selected) this.onChrome?.(); // the card's Detail is offered while a machine with levels is chosen
  }

  rebuildMachine(id) {
    const shown = this.shapeMeshes?.get(id);
    if (!shown) return;
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

  setIsolate() {}

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
    const tray = this.layout.trays.find((item) => item.group === this.focusGroup);
    if (tray) this.flyToBox(new THREE.Box3(new THREE.Vector3(tray.x - tray.w / 2, 0, tray.z - tray.d / 2), new THREE.Vector3(tray.x + tray.w / 2, 4, tray.z + tray.d / 2)));
    else this.stage.rig?.flyTo?.(this.homeView(), 900);
  }

  /** A door from another view (the viewer's openDoor, `value`): the machine it names is chosen. */
  setFinding(id) {
    if (id && this.has(id)) this.onShown?.(id);
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
    const quiet = (id) => Boolean(this.selected) && id !== this.selected;
    if (this.flatNames) {
      this.flatNames.material.transparent = true;
      this.flatNames.material.opacity = this.selected ? 0.12 : 1;
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
  }

  /** A move toward what was chosen: its shape or card with its neighbours in the tray. */
  focus(id) {
    const owner = this.partOf(id) || this.measuredPart(id)?.owner || id;
    const entry = this.layout?.items.find((item) => item.id === owner);
    if (!entry) return;
    const pad = entry.type === "card" ? 6 : Math.max(2, Math.max(entry.w, entry.h) * 0.6);
    const box = new THREE.Box3(new THREE.Vector3(entry.x - entry.w / 2 - pad, entry.y, entry.z - entry.d / 2 - pad), new THREE.Vector3(entry.x + entry.w / 2 + pad, entry.y + entry.h + LIFT + 1, entry.z + entry.d / 2 + pad));
    this.flyToBox(box);
  }

  flyToBox(box) {
    const { stage } = this, rig = stage.rig;
    if (!rig?.flyTo || box.isEmpty()) return;
    this.homeHeld = null;
    const view = this.fitOnScreen(box, 0.1);
    rig.flyTo(view, 1000);
    this.focused = { box: box.clone(), insets: JSON.stringify(stage.insets || {}), until: now() + 1600 };
  }

  update(dt = 16) {
    if (this.stage.width && this.stage.height && columnsFor(this.stage) !== this.columns) {
      this.columns = columnsFor(this.stage);
      this.build();
      this.afterBuild(true);
      return true;
    }
    if (this.relayout) {
      this.relayout = false;
      this.build();
      this.afterBuild(!this.selected);
      return true;
    }
    const held = this.homeHeld, insets = JSON.stringify(this.stage.insets || {});
    if (held && !this.selected && now() < held.until && held.insets !== insets) {
      held.insets = insets;
      this.stage.rig?.setView?.(this.homeView());
    }
    const focused = this.focused;
    if (focused && now() < focused.until && focused.insets !== insets) this.flyToBox(focused.box);
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
    return moving;
  }

  applyPalette(palette) {
    this.palette = palette;
    if (!this.layout) return;
    this.applyColours((item) => !this.query || this.catalogue.passes(item, this.query));
    for (const [id, { group }] of this.built || []) {
      if (group) this.paint(group);
      this.shadeParts(id);
    }
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
    this.stopLook?.();
    this.stopRestore?.();
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
