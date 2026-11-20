// The organelles of the species shown, on a shelf of the Machines view (schema/MACHINE_CATALOGUE.md, "Organelles").
// Asked for on 20 November 2026: the organelles stand in the Machines view as the machines do, on a shelf above the
// bench, drawn with the 3D models the Cell view already has, at the bench's one scale.
//
// Each organelle is drawn by the Cell view's own builders, imported and called as they are (cell_parts.js, buildCell,
// with the part modules of the structures and the mitochondria; nothing of them is copied here): the cell's parts are
// built in the cell's own frame by a context of this view's, the organelle's part is lifted out of the cell, centred,
// and set at the size its species' file states. Which of the model's widths that size sets is said for each kind
// (MODELS): the nucleus's width, the reticulum's sheet, a Golgi cisterna's width, a mitochondrion's width and length.
// Every other proportion of the model is the Cell view's choice, and the panel says so. Nothing here names a species.

import * as THREE from "../three.js";
import { buildCell } from "./cell_parts.js";
import { CUT, STYLE } from "./cell_layout.js";
import { CISTERNAE } from "./cell_structures.js";
import structures from "./parts/structures.js";
import mitochondria from "./parts/mitochondria.js";
import scenery from "./parts/scenery.js";
import { UNIT_NM } from "./machines_layout.js";

const UP = new THREE.Vector3(0, 1, 0);

/**
 * For each organelle kind: the part of the Cell view that draws it, in which of the Cell view's two pictures ("real", to
 * scale; "schematic", parts enlarged), the measure its species' file sets, and the model's own measure of it, in the
 * cell's frame. `one` takes the first of the parts the builder makes (a mitochondrion of the three cut open at the surface).
 */
export const MODELS = {
  nucleus: { part: "nucleus", hue: "bioNucleus", mode: "real", sets: "across", model: () => 2 * STYLE.real.nucleusRadius, words: "the nucleus as the Cell view draws it to scale: its double envelope opened by a wedge, its pores as dots, its nucleolus and its chromatin" },
  "endoplasmic-reticulum": { part: "er", hue: "bioEr", mode: "real", sets: "thick", model: () => STYLE.real.er.thickness, lines: false, words: "the rough endoplasmic reticulum as the Cell view draws it to scale: sheets folded to and fro in two arms, without the tubules it draws through the cell" },
  "golgi-apparatus": { part: "golgi", hue: "bioGolgi", mode: "real", sets: "cisterna", model: () => Math.max(...CISTERNAE.real), words: "the Golgi apparatus as the Cell view draws it to scale in an animal cell: a ribbon of stacks of curved cisternae, with vesicles budding from their rims" },
  // A plant cell's chloroplast: one of the lens-shaped bodies the Cell view's scenery builder lines the cell with (cell_scenery.js).
  chloroplast: { part: "scenery:chloroplasts", hue: "bioChloroplast", mode: "real", sets: "across", instance: true, words: "a chloroplast as the Cell view draws it in a plant cell: a lens-shaped body, a little flatter than it is wide" },
  mitochondrion: { part: "mitochondria", hue: "bioMito", mode: "schematic", sets: "capsule", one: true, words: "one mitochondrion as the Cell view draws those cut open at the cell's surface: its outer membrane opened from above, its matrix and the folds of its inner membrane" },
};

/** The size an organelle is drawn at, in the view's units (one is ten nanometres), from its catalogue entry's size; null where none is in hand. */
export function drawnSize(size) {
  if (!size) return null;
  const middle = (values) => (values.length > 1 ? (values[0] + values[values.length - 1]) / 2 : values[0]);
  const um = (values) => (middle(values) * 1000) / UNIT_NM;
  if (size.shape === "sphere" || size.shape === "lens") return { across: um(size.across_um) };
  if (size.shape === "stack") return { cisterna: um(size.across_um) };
  if (size.shape === "sheet") return { thick: middle(size.thick_nm) / UNIT_NM };
  if (size.shape === "capsule") return { across: um(size.across_um), long: um(size.long_um) };
  return null;
}

/**
 * A context for the Cell view's builders (as cell.js gives its parts, in the few calls they make): each part's objects
 * kept by its name, its materials with the hue and shade they ask for (coloured from the page's palette in `paint`), a
 * material that asks to be cut by the cell's cut keeping the cut's plane to be set where the organelle stands. The look's
 * own effects (a rim, a texture, a jostle) are the Cell view's resting look and are not drawn here.
 */
function contextFor(known) {
  const parts = new Map(), materials = [];
  const keep = (material, look) => {
    material.userData = { ...material.userData, look };
    materials.push(material);
    return material;
  };
  let proxy = null;
  const part = (name, anchor) => {
    const made = { name, anchor: anchor ? anchor.clone() : new THREE.Vector3(), objects: [], priority: 0 };
    made.material = ({ hue = null, opacity = 1, shade = 0, roughness = 0.42, side = THREE.FrontSide, clip = false, depthWrite, flat = false } = {}) =>
      keep(new THREE.MeshStandardMaterial({ roughness, metalness: 0, flatShading: flat, side, transparent: opacity < 1, opacity, depthWrite: depthWrite ?? opacity === 1 }), { hue, shade, clip });
    made.points = ({ hue = null, shade = 0, size = 1.6, opacity = 0.9 } = {}) => keep(new THREE.PointsMaterial({ size, sizeAttenuation: false, transparent: true, opacity, depthWrite: false }), { hue, shade });
    made.lineMaterial = ({ hue = null, opacity = 0.8 } = {}) => keep(new THREE.LineBasicMaterial({ transparent: true, opacity, depthWrite: false }), { hue, shade: 0 });
    made.proxyMaterial = () => (proxy ??= new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false }));
    made.add = (...objects) => made.objects.push(...objects);
    if (!parts.has(name)) parts.set(name, []);
    parts.get(name).push(made);
    return made;
  };
  // Scenery wears its colour in life where it has one (a chloroplast's green), else the page's neutral; what can be chosen is kept by its id.
  const neutral = ({ opacity = 0.5, colour = "ghost", natural = null, side = THREE.FrontSide, depthWrite } = {}) => keep(new THREE.MeshStandardMaterial({ roughness: 0.45, metalness: 0, side, transparent: opacity < 1, opacity, depthWrite: depthWrite ?? opacity === 1 }), { hue: natural || colour, shade: 0 });
  const scenery = (object, id) => {
    if (!known.includes(id)) return;
    if (!parts.has(id)) parts.set(id, []);
    parts.get(id).push({ name: id, objects: [object] });
  };
  const ctx = { part, scale: part, known: (name) => known.includes(name), neutral, neutralPoints: () => new THREE.PointsMaterial(), neutralLine: () => new THREE.LineBasicMaterial(), illustrate: () => {}, scenery, sprite: () => {} };
  return { ctx, parts, materials };
}

/**
 * The Cell view's models of a species' organelles, each lifted out of the cell it is built in: { kind -> { root, box,
 * model, planes, materials } }, in the cell's frame (`root` holds the part's objects where the cell put them; `box` is
 * their extent; `model` the Cell view's own measure the size sets; `planes` the clipping planes its materials share).
 * `cell` is what buildCell takes of the species (its shape and parts); `kinds` the organelle kinds wanted.
 */
export function organelleModels(cell, kinds) {
  const out = new Map();
  const byMode = new Map();
  for (const kind of kinds) {
    const model = MODELS[kind];
    if (!model) continue;
    if (!byMode.has(model.mode)) byMode.set(model.mode, []);
    byMode.get(model.mode).push(kind);
  }
  for (const [mode, wanted] of byMode) {
    const names = wanted.map((kind) => MODELS[kind].part);
    const own = contextFor(names), ignored = contextFor([]);
    // The structures (nucleus, ER, Golgi) from their own stream of chance; the mitochondria from the layout's, as the Cell view's
    // builder calls them, so that each model is the one its own builder draws.
    const modules = [...(names.some((name) => name !== "mitochondria" && !name.startsWith("scenery:")) ? [structures] : []), ...(names.includes("mitochondria") ? [mitochondria] : []), ...(names.some((name) => name.startsWith("scenery:")) ? [scenery] : [])];
    const handles = buildCell(own.ctx, ignored.ctx, mode, cell, modules);
    const u = handles.frame.u;
    for (const kind of wanted) {
      const spec = MODELS[kind];
      const made = own.parts.get(spec.part) || [];
      let objects = made.flatMap((part) => part.objects);
      if (spec.one) {
        objects = objects.filter((object) => object.isGroup).slice(0, 1);
        // Lying along the shelf (its long axis along x), as the Cell view builds it before it turns it in the cell; its height kept, for the cut.
        for (const object of objects) object.rotation.set(0, 0, 0);
      }
      if (spec.instance) {
        // One of many: the first copy of an instanced shape, at its own size, lying as it was built (its flat axis upright).
        const many = objects.find((object) => object.isInstancedMesh);
        if (!many) continue;
        const matrix = new THREE.Matrix4(), place = new THREE.Vector3(), turn = new THREE.Quaternion(), size = new THREE.Vector3();
        many.getMatrixAt(0, matrix);
        matrix.decompose(place, turn, size);
        const one = new THREE.Mesh(many.geometry, many.material);
        one.scale.copy(size);
        objects = [one];
      }
      if (spec.lines === false) objects = objects.filter((object) => !object.isLine && !object.isLineSegments && !object.isPoints);
      if (!objects.length) continue;
      const root = new THREE.Group();
      for (const object of objects) root.add(object);
      // Picked as the organelle (its holder carries the id): the Cell view's own filters of a press are for its wedge in the cell.
      root.traverse((object) => {
        delete object.userData.pickFilter;
        delete object.userData.pick;
      });
      const materials = new Set();
      root.traverse((object) => {
        for (const material of [object.material].flat().filter(Boolean)) {
          materials.add(material);
          if (material.userData?.twin) materials.add(material.userData.twin);
        }
      });
      // The planes its materials are cut by: the nucleus's wedge (made in the cell's world, its frame times u), and the cell's cut
      // for a part that asks for it (in the frame), each made once and moved with the organelle (placeModel).
      const planes = [];
      const cut = new THREE.Plane(new THREE.Vector3(0, -1, 0), CUT);
      let cutUsed = false;
      for (const material of materials) {
        if (material.userData?.look?.clip) {
          material.clippingPlanes = [cut];
          cutUsed = true;
        } else for (const plane of material.clippingPlanes || []) if (!planes.some((entry) => entry.plane === plane)) planes.push({ plane, scale: 1 / u });
      }
      if (cutUsed) planes.push({ plane: cut, scale: 1 });
      const box = boxOf(root);
      // The model's own measure: given by its builder's constants, or, for a mitochondrion, its body's width and length as built.
      const measure = spec.model ? { [spec.sets]: spec.model() } : spec.sets === "across" ? { across: Math.max(box.max.x - box.min.x, box.max.z - box.min.z) } : capsuleOf(root);
      out.set(kind, { kind, root, box, measure, planes, materials: [...materials], words: spec.words, mode });
    }
  }
  return out;
}

/** The extent of a group's drawn objects, each copy of an instanced shape placed. */
function boxOf(root) {
  const box = new THREE.Box3(), matrix = new THREE.Matrix4(), one = new THREE.Box3();
  root.updateMatrixWorld(true);
  root.traverse((object) => {
    if (!object.geometry) return;
    object.geometry.computeBoundingBox();
    if (object.isInstancedMesh) {
      for (let index = 0; index < object.count; index++) {
        object.getMatrixAt(index, matrix);
        box.union(one.copy(object.geometry.boundingBox).applyMatrix4(matrix).applyMatrix4(object.matrixWorld));
      }
    } else box.union(one.copy(object.geometry.boundingBox).applyMatrix4(object.matrixWorld));
  });
  return box;
}

/** A mitochondrion as built: its body's length (its long axis) and width, in the cell's frame. */
function capsuleOf(root) {
  const body = root.children[0]?.children.find((object) => object.geometry?.type === "CapsuleGeometry");
  if (!body) return null;
  body.geometry.computeBoundingBox();
  const size = body.geometry.boundingBox.getSize(new THREE.Vector3());
  const long = Math.max(size.x, size.y, size.z), across = Math.min(size.x, size.y, size.z);
  return { long, across };
}

/**
 * How a model is scaled to the size its species' file states: along x, y and z, in the view's units for one of the cell's
 * frame. A sphere, a sheet and a stack keep the model's proportions; a mitochondrion takes the stated width across and
 * the stated length along its long axis (x, as the Cell view lays it).
 */
export function scaleFor(model, drawn) {
  if (!model?.measure || !drawn) return null;
  const { measure } = model;
  if (drawn.across !== undefined && drawn.long !== undefined && measure.long) return new THREE.Vector3(drawn.long / measure.long, drawn.across / measure.across, drawn.across / measure.across);
  for (const key of ["across", "thick", "cisterna"]) if (drawn[key] !== undefined && measure[key]) return new THREE.Vector3().setScalar(drawn[key] / measure[key]);
  return null;
}

/**
 * Sets a model on the shelf: centred on its place, its lowest point on the shelf, turned about the upright by `turn`, and
 * scaled; its clipping planes are moved with it once, so that the nucleus's wedge and a mitochondrion's cut open where they
 * did in the cell. Returns the holder (its id to be picked), and the extent it takes on the shelf, in the view's units.
 */
export function placeModel(model, { scale, turn = 0, at = new THREE.Vector3() }) {
  const centre = model.box.getCenter(new THREE.Vector3()).setY(model.box.min.y);
  const holder = new THREE.Group(), inner = new THREE.Group();
  inner.position.copy(centre).negate();
  inner.add(model.root);
  holder.add(inner);
  holder.position.copy(at);
  holder.quaternion.setFromAxisAngle(UP, turn);
  holder.scale.copy(scale);
  holder.updateMatrixWorld(true);
  const matrix = new THREE.Matrix4(), toWorld = new THREE.Matrix4().copy(holder.matrixWorld).multiply(new THREE.Matrix4().makeTranslation(-centre.x, -centre.y, -centre.z));
  for (const { plane, scale: factor } of model.planes) plane.applyMatrix4(matrix.copy(toWorld).multiply(new THREE.Matrix4().makeScale(factor, factor, factor)));
  const size = model.box.getSize(new THREE.Vector3()).multiply(scale);
  return { holder, size };
}

/** Colours the materials of a model from the page's palette: each its hue, lighter or darker by its shade, as the Cell view's are. */
export function paintModel(model, palette = {}) {
  const white = new THREE.Color(1, 1, 1), black = new THREE.Color(0, 0, 0);
  for (const material of model.materials) {
    const look = material.userData?.look;
    if (!look || !material.color) continue;
    const colour = new THREE.Color(palette[look.hue] || palette.ghost || "#8a96a3");
    if (look.shade > 0) colour.lerp(white, look.shade);
    else if (look.shade < 0) colour.lerp(black, -look.shade);
    material.color.copy(colour);
  }
}

/** What a frame pays to draw a group: draws and triangles of what it shows. */
export function costOf(root) {
  let draws = 0, triangles = 0;
  root.traverseVisible((object) => {
    if (!(object.isMesh || object.isLine || object.isPoints)) return;
    const copies = object.isInstancedMesh ? object.count : 1;
    if (!copies) return;
    draws += 1;
    if (object.isMesh) triangles += ((object.geometry.index ? object.geometry.index.count : object.geometry.attributes.position.count) / 3) * copies;
  });
  return { draws, triangles: Math.round(triangles) };
}
