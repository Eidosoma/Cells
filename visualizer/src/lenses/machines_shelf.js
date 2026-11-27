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
import { seeded } from "./parts/geometry.js";

const UP = new THREE.Vector3(0, 1, 0);

/**
 * For each organelle kind: the part of the Cell view that draws it, in which of the Cell view's two pictures ("real", to
 * scale; "schematic", parts enlarged), the measure its species' file sets, and the model's own measure of it, in the
 * cell's frame. `one` takes the first of the parts the builder makes (a mitochondrion of the three cut open at the surface).
 */
export const MODELS = {
  nucleus: { part: "nucleus", hue: "bioNucleus", mode: "real", sets: "across", model: () => 2 * STYLE.real.nucleusRadius, words: "the nucleus as the Cell view draws it to scale: its double envelope opened by a wedge, its pores as dots, its nucleolus and its chromatin" },
  "endoplasmic-reticulum": { part: "er", hue: "bioEr", mode: "real", sets: "thick", model: () => STYLE.real.er.thickness, lines: false, words: "the rough endoplasmic reticulum as the Cell view draws it to scale: sheets folded to and fro in two arms, without the tubules it draws through the cell" },
  "golgi-apparatus": { part: "golgi", hue: "bioGolgi", mode: "real", sets: "cisterna", model: () => Math.max(...CISTERNAE.real), words: `the Golgi apparatus as the Cell view draws it to scale in an animal cell: a ribbon of stacks, each of ${STYLE.real.golgi.count} curved cisternae, with vesicles budding from their rims` },
  // A plant cell's chloroplast: one of the lens-shaped bodies the Cell view's scenery builder lines the cell with (cell_scenery.js).
  chloroplast: { part: "scenery:chloroplasts", hue: "bioChloroplast", mode: "real", sets: "across", instance: true, words: "a chloroplast as the Cell view draws it in a plant cell: a lens-shaped body, a little flatter than it is wide" },
  mitochondrion: { part: "mitochondria", hue: "bioMito", mode: "schematic", sets: "capsule", one: true, words: "one mitochondrion as the Cell view draws those cut open at the cell's surface: its outer membrane opened from above, its matrix and the folds of its inner membrane" },
  // A centriole: one of the two barrels of the centrosome that the Cell view draws as scenery beside an animal cell's nucleus, built
  // with its structures (cell_structures.js) and handed to the context's scenery hook; the upright barrel, laid on its side.
  centriole: { part: "scenery:centrosome", hue: "edge", recolour: true, mode: "real", sets: "barrel", barrel: true, words: "one centriole as the Cell view draws each of the two in an animal cell's centrosome: a short barrel of nine rods, laid on its side" },
};
/** The Cell view's scenery that its structures' builder hands on (not the scenery part module): an animal cell's centrosome. */
const OF_STRUCTURES = new Set(["scenery:centrosome"]);

/**
 * The organelles the Cell view has no model of: a simple model of each, built here (an illustration), at one unit across, its
 * measure the whole's width (`across`), or the body's where it carries tubules. Asked for on 20 November 2026: the rest of the
 * organelles as 3D models, not flat cards. Each claims no structure beyond what its plain line and its source give; `choice` is
 * what the panel says is the picture's. `make`: `shell`, a sphere of `layers` membranes cut open over a darker lumen; `coat`, a
 * sphere studded with knobs for its coat; `tubules`, a sphere with short tubules; `ball`, a plain sphere.
 */
export const SIMPLE = {
  "plasmodial-nucleus": { make: "nucleus", hue: "bioNucleus", words: "a cutaway nucleus with a double envelope and nucleolus", choice: "pore placement, the opening and interior proportions are illustrative" },
  "tubular-mitochondrion": { make: "tubular-cristae", hue: "bioMito", words: "a cutaway ellipsoid with tubular cristae and a central nucleoid", choice: "the arrangement of the cristae is illustrative" },
  "extracellular-vesicle": { make: "shell", hue: "bioWater", words: "a cutaway extracellular vesicle", choice: "the membrane thickness and opening are illustrative" },
  "envelope-section": { make: "envelope", hue:"bioFuel", words:"a membrane patch beneath a raised S-layer lattice", choice:"the lateral extent and motif spacing are illustrative" },
  "cell-bridge": { make: "bridge", hue: "bioCell", words: "an open-ended bridge with an outer coat and inner membrane", choice: "the layer spacing and longitudinal cut are illustrative" },
  lysosome: { make: "shell", layers: 1, hue: "bioSignal", words: "a sphere of one membrane, cut open over its darker lumen", choice: "the membrane's thickness, the lumen's shade and where it is cut open are the picture's choice" },
  peroxisome: { make: "shell", layers: 1, hue: "bioFuel", words: "a sphere of one membrane, cut open over its darker lumen", choice: "the membrane's thickness, the lumen's shade and where it is cut open are the picture's choice" },
  autophagosome: { make: "shell", layers: 2, hue: "bioPump", words: "a sphere of two membranes, cut open over its darker lumen", choice: "its cargo is not drawn, and the membranes' thickness and the gap between them, the lumen's shade and where it is cut open are the picture's choice" },
  "copi-vesicle": { make: "coat", hue: "bioGolgi", words: "a small sphere of membrane studded with knobs that stand for its coat", choice: "the size above is the whole's, coat included, and how many knobs, how large and how thick the coat is are the picture's choice" },
  "endocytic-vesicle": { make: "tubules", hue: "bioWater", words: "a small sphere with short tubules, for the vesicles and tubules its source measured", choice: "the size above is the sphere's, and how many tubules, how long and how wide are the picture's choice" },
  "lipid-droplet": { make: "ball", hue: "bioFuel", shade: 0.35, words: "a plain sphere", choice: "its surface and shade are the picture's choice" },
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
    const ofScenery = (name) => name.startsWith("scenery:") && !OF_STRUCTURES.has(name); // drawn by the scenery part module
    const modules = [...(names.some((name) => name !== "mitochondria" && !ofScenery(name)) ? [structures] : []), ...(names.includes("mitochondria") ? [mitochondria] : []), ...(names.some(ofScenery) ? [scenery] : [])];
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
      if (spec.barrel) {
        // One centriole: the rods of the centrosome's upright barrel (each rod's own axis upright; the other barrel lies across it),
        // told apart by their direction, not by the order they were made in; the cloud round both is left out. Laid on its side.
        const rods = objects.flatMap((object) => (object.isInstancedMesh ? [object] : object.children.filter((child) => child.isInstancedMesh)))[0];
        if (!rods) continue;
        const matrix = new THREE.Matrix4(), axis = new THREE.Vector3(), upright = [];
        for (let index = 0; index < rods.count; index++) {
          rods.getMatrixAt(index, matrix);
          if (axis.setFromMatrixColumn(matrix, 1).normalize().y > 0.9) upright.push(matrix.clone());
        }
        if (!upright.length) continue;
        const one = new THREE.InstancedMesh(rods.geometry, rods.material, upright.length);
        upright.forEach((value, index) => one.setMatrixAt(index, value));
        one.computeBoundingSphere();
        if (spec.recolour && rods.material.userData?.look) rods.material.userData.look = { ...rods.material.userData.look, hue: spec.hue };
        const lying = new THREE.Group();
        lying.rotation.z = -Math.PI / 2;
        lying.add(one);
        objects = [lying];
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
      // The model's own measure: given by its builder's constants, or, for a mitochondrion, its body's width and length as built,
      // or, for a centriole's barrel, its length (along x, as it lies) and its width as built.
      const measure = spec.model ? { [spec.sets]: spec.model() } : spec.sets === "across" ? { across: Math.max(box.max.x - box.min.x, box.max.z - box.min.z) } : spec.barrel ? { long: box.max.x - box.min.x, across: Math.max(box.max.y - box.min.y, box.max.z - box.min.z) } : capsuleOf(root);
      out.set(kind, { kind, root, box, measure, planes, materials: [...materials], words: spec.words, mode });
    }
  }
  return out;
}

/**
 * A simple model of an organelle the Cell view has no model of (SIMPLE), at one unit across, in the shape `placeModel` and
 * `paintModel` take: { kind, root, box, measure, planes, materials, words }. A kind with no entry there stands as a plain
 * sphere, or a capsule where its size gives a length. Every material carries its hue and shade (`look`), so a change of
 * theme repaints it. Its cut is made in the geometry (a sphere with a wedge left out toward the camera), not by clipping.
 */
export function simpleModel(kind, { long = 1 } = {}) {
  const spec = SIMPLE[kind] || { make: long > 1 ? "capsule" : "ball", hue: "ghost", words: long > 1 ? "a plain capsule" : "a plain sphere", choice: "" };
  const materials = [];
  const material = (shade = 0, { side = THREE.FrontSide, roughness = 0.42, hue = spec.hue } = {}) => {
    const made = new THREE.MeshStandardMaterial({ roughness, metalness: 0.03, side });
    made.userData.look = { hue, shade: (spec.shade || 0) + shade };
    materials.push(made);
    return made;
  };
  const root = new THREE.Group();
  // The wedge left out of a shell faces the bench's camera (toward +z, a little to one side, as the nucleus's is opened).
  const wedge = 1.9, open = { start: Math.PI / 2 + wedge / 2 + 0.25, length: Math.PI * 2 - wedge };
  const shell = (radius, shade) => new THREE.Mesh(new THREE.SphereGeometry(radius, 36, 20, open.start, open.length), material(shade, { side: THREE.DoubleSide }));
  if (spec.make === "envelope") {
    const membrane=new THREE.Mesh(new THREE.BoxGeometry(3.4,.09,2.12),material(.04,{hue:"bioCell"}));
    membrane.position.y=-.045;
    root.add(membrane);
    const motif=new THREE.TorusGeometry(.29,.07,8,6);
    const coat=new THREE.InstancedMesh(motif,material(.12),20), stamp=new THREE.Object3D();
    stamp.rotation.x=Math.PI/2;
    for (let row=0; row<4; row++) for (let col=0; col<5; col++) {
      stamp.position.set((col-2)*.57+(row%2-.5)*.28,1,(row-1.5)*.49);
      stamp.updateMatrix();
      coat.setMatrixAt(row*5+col,stamp.matrix);
    }
    root.add(coat);
  } else if (spec.make === "bridge") {
    for (const [radius, opening, hue] of [[.49, 1.85, "bioFuel"], [.41, 1.23, "bioCell"]]) {
      const tube = new THREE.CylinderGeometry(radius,radius,long,48,1,true,opening/2,2*Math.PI-opening);
      root.add(new THREE.Mesh(tube.rotateZ(Math.PI/2),material(-.1,{side:THREE.DoubleSide,hue})));
    }
    // An oblique cut exposes the inner layer. A repeated relief distinguishes
    // the S-layer from the membrane even at the same magnification.
    const columns=Math.max(1,Math.floor(long/.20)), rows=12, stamp=new THREE.Object3D();
    const ridges=new THREE.InstancedMesh(new THREE.TorusGeometry(.077,.014,4,6),
      material(.09,{hue:"bioFuel"}),columns*rows);
    for (let col=0;col<columns;col++) for (let row=0;row<rows;row++) {
      const angle=1.02+(row+.5*(col%2))*(2*Math.PI-2.04)/rows;
      const normal=new THREE.Vector3(0,Math.sin(angle),Math.cos(angle));
      stamp.position.copy(normal).multiplyScalar(.495);
      stamp.position.x=long*((col+.5)/columns-.5);
      stamp.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal);
      stamp.updateMatrix();
      ridges.setMatrixAt(col*rows+row,stamp.matrix);
    }
    root.add(ridges);
  } else if (spec.make === "nucleus" || spec.make === "tubular-cristae") {
    root.add(shell(.5,.12),shell(.46,-.22));
    const nucleus = spec.make === "nucleus";
    if (nucleus) {
      const random=seeded(5791), stamp=new THREE.Object3D();
      const pores=new THREE.InstancedMesh(new THREE.TorusGeometry(.022,.005,5,9),material(-.27),100);
      for (let i=0; i<pores.count; i++) {
        const a=open.start+random()*open.length, y=2*random()-1, r=Math.sqrt(1-y*y);
        const normal=new THREE.Vector3(-r*Math.cos(a),y,r*Math.sin(a));
        stamp.position.copy(normal).multiplyScalar(.5);
        stamp.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),normal);
        stamp.updateMatrix();
        pores.setMatrixAt(i,stamp.matrix);
      }
      root.add(pores);
    }
    const centre = new THREE.Mesh(new THREE.SphereGeometry(nucleus ? .16 : .085,20,14), material(-.4));
    centre.scale.set(nucleus ? 1 : 2.6,1,1);
    root.add(centre);
    if (!nucleus) {
      for (let i=0;i<14;i++) {
        const a=i*2.39996, x=(i%5-2)*.074;
        const y=.3*Math.cos(a), z=.3*Math.sin(a);
        const path = new THREE.QuadraticBezierCurve3(new THREE.Vector3(x,y,z),new THREE.Vector3(x+.10,y*.55,z*.55),new THREE.Vector3(x+.09,y*.35,z*.46));
        root.add(new THREE.Mesh(new THREE.TubeGeometry(path,8,.022,6),material(.22)));
      }
      root.scale.x=long;
    }
  } else if (spec.make === "shell") {
    // Each membrane a thin shell (its outer and inner faces), the lumen a darker sphere inside, seen through the opening.
    const step = 0.075, layers = spec.layers || 1;
    for (let layer = 0; layer < layers; layer++) {
      const outer = 0.5 - layer * 2.2 * step;
      root.add(shell(outer, 0.08), shell(outer - step * 0.55, -0.05));
    }
    root.add(new THREE.Mesh(new THREE.SphereGeometry(0.5 - layers * 2.2 * step + step * 0.6, 28, 18), material(-0.45, { roughness: 0.7 })));
  } else if (spec.make === "coat") {
    // The vesicle's membrane, and knobs spread evenly over it (a Fibonacci lattice), reaching half a unit from its middle.
    root.add(new THREE.Mesh(new THREE.SphereGeometry(0.37, 32, 22), material(0.15)));
    const count = 72, knobs = new THREE.InstancedMesh(new THREE.SphereGeometry(0.1, 8, 6), material(-0.12), count), place = new THREE.Object3D();
    for (let index = 0; index < count; index++) {
      const y = 1 - (2 * (index + 0.5)) / count, ring = Math.sqrt(1 - y * y), turn = index * Math.PI * (3 - Math.sqrt(5));
      place.position.set(Math.cos(turn) * ring, y, Math.sin(turn) * ring).multiplyScalar(0.4);
      place.updateMatrix();
      knobs.setMatrixAt(index, place.matrix);
    }
    knobs.computeBoundingSphere();
    root.add(knobs);
  } else if (spec.make === "tubules") {
    // The sphere, a unit across, and three short tubules leaving it.
    root.add(new THREE.Mesh(new THREE.SphereGeometry(0.5, 36, 24), material(0)));
    for (const [x, y, z] of [[1, 0.25, -0.2], [-0.7, 0.1, -0.75], [-0.35, 0.35, 0.85]]) {
      const way = new THREE.Vector3(x, y, z).normalize(), tube = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.42, 4, 14), material(0.1));
      tube.quaternion.setFromUnitVectors(UP, way);
      tube.position.copy(way).multiplyScalar(0.62);
      root.add(tube);
    }
  } else if (spec.make === "capsule") {
    root.add(new THREE.Mesh(new THREE.CapsuleGeometry(0.5, long - 1, 8, 24).rotateZ(Math.PI / 2), material(0)));
  } else root.add(new THREE.Mesh(new THREE.SphereGeometry(0.5, 40, 28), material(0, { roughness: 0.3 })));
  const box = boxOf(root);
  const measure = spec.make === "envelope" ? {thick:1} : ["bridge","tubular-cristae","capsule"].includes(spec.make) ? { across: 1, long } : { across: 1 };
  return { kind, root, box, measure, planes: [], materials, words: spec.words, choice: spec.choice, simple: true };
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
