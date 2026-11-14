// Geometry for the cell lens. Every shape built here is either bound to a capability
// from the scene file (through ctx.part) or is neutral illustration (ctx.neutral).
// Nothing is drawn that looks like a capability without being one.

import * as THREE from "../three.js";
import { glyphSprite } from "../core/materials.js";

export const R = 10; // The cell's radius; every other length is relative to it.

// The cutaway removes the octant x > 0, y > 0, z > 0.
export const CUT_PLANES = [
  new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0),
  new THREE.Plane(new THREE.Vector3(0, -1, 0), 0),
  new THREE.Plane(new THREE.Vector3(0, 0, -1), 0),
];
export const inCut = (point) => point.x > 0 && point.y > 0 && point.z > 0;

/** A small repeatable random source, so the cell looks the same on every load. */
export function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function unit(random) {
  const z = random() * 2 - 1, angle = random() * Math.PI * 2, r = Math.sqrt(1 - z * z);
  return new THREE.Vector3(r * Math.cos(angle), z, r * Math.sin(angle));
}

const UP = new THREE.Vector3(0, 1, 0);
const along = (direction) => new THREE.Quaternion().setFromUnitVectors(UP, direction.clone().normalize());

/** Many copies of one shape, each at a position with its long axis along a direction. */
function instanced(geometry, material, placements) {
  const mesh = new THREE.InstancedMesh(geometry, material, placements.length);
  const matrix = new THREE.Matrix4(), scale = new THREE.Vector3(1, 1, 1);
  placements.forEach((placement, index) => {
    scale.setScalar(placement.scale ?? 1);
    matrix.compose(placement.position, placement.direction ? along(placement.direction) : new THREE.Quaternion(), scale);
    mesh.setMatrixAt(index, matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

// ------------------------------------------------------------------ one cell

export function buildCell(ctx, studsCtx) {
  const random = seeded(7);

  // Membrane: a translucent shell with one octant cut away, and a rim along the cut.
  const membrane = ctx.part("membrane", new THREE.Vector3(-6.4, 6.6, 4.2));
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(R, 96, 64),
    membrane.material({ opacity: 0.36, side: THREE.DoubleSide, clip: true, roughness: 0.3, depthWrite: true })
  );
  shell.userData.pickFilter = (hit) => !inCut(hit.point);
  membrane.add(shell);
  const edge = studsCtx.part("membrane");
  const rimMaterial = edge.material({ roughness: 0.4, shade: -0.18 });
  for (const turn of [new THREE.Euler(0, 0, 0), new THREE.Euler(Math.PI / 2, 0, 0), new THREE.Euler(0, -Math.PI / 2, 0)]) {
    const rim = new THREE.Mesh(new THREE.TorusGeometry(R, 0.15, 10, 48, Math.PI / 2), rimMaterial);
    rim.rotation.copy(turn);
    edge.add(rim);
  }
  // Charge across the membrane: plus outside, minus inside, along the cut edge.
  for (let index = 0; index < 7; index++) {
    const angle = ((index + 0.5) / 7) * (Math.PI / 2);
    const direction = new THREE.Vector3(Math.cos(angle), Math.sin(angle), 0);
    studsCtx.sprite(edge, "+", direction.clone().multiplyScalar(R + 0.75), 0.8);
    studsCtx.sprite(edge, "−", direction.clone().multiplyScalar(R - 0.8), 0.8);
  }

  // Cytoplasm: the three cut faces, and small molecules in the opened octant.
  const chemistry = ctx.part("cytoplasm", new THREE.Vector3(7.0, 0.3, 4.6));
  const faceMaterial = chemistry.material({ opacity: 0.2, side: THREE.DoubleSide, roughness: 1, depthWrite: false });
  for (const turn of [new THREE.Euler(0, 0, 0), new THREE.Euler(Math.PI / 2, 0, 0), new THREE.Euler(0, -Math.PI / 2, 0)]) {
    const face = new THREE.Mesh(new THREE.CircleGeometry(R - 0.02, 48, 0, Math.PI / 2), faceMaterial);
    face.rotation.copy(turn);
    face.renderOrder = 1;
    chemistry.add(face);
  }
  const specks = [];
  while (specks.length < 46) {
    const point = new THREE.Vector3(random() * 8.6, random() * 8.6, random() * 8.6);
    if (point.length() < 8.8 && point.distanceTo(NUCLEUS) > 4.3) specks.push({ position: point, scale: 0.6 + random() * 0.8 });
  }
  chemistry.add(instanced(new THREE.SphereGeometry(0.1, 8, 6), chemistry.material({ opacity: 0.85 }), specks));

  // Channels and pumps stud the membrane. Each stands for a population, not single proteins.
  const studs = (count, minGap) => {
    const placed = [];
    let guard = 0;
    while (placed.length < count && guard++ < 4000) {
      const direction = unit(random);
      if (direction.x > -0.12 && direction.y > -0.12 && direction.z > -0.12) continue; // keep clear of the cut
      if (placed.some((other) => other.direction.angleTo(direction) < minGap)) continue;
      placed.push({ direction, position: direction.clone().multiplyScalar(R) });
    }
    return placed;
  };
  const channels = studsCtx.part("channels", new THREE.Vector3(-8.9, 2.4, 4.4));
  channels.add(instanced(new THREE.CylinderGeometry(0.3, 0.3, 0.72, 12), channels.material({ roughness: 0.45, shade: -0.12 }), studs(44, 0.23)));
  const pumps = studsCtx.part("pumps", new THREE.Vector3(-4.2, -8.4, 4.6));
  pumps.add(instanced(new THREE.CapsuleGeometry(0.46, 0.5, 6, 14), pumps.material({ roughness: 0.45, shade: 0.16 }), studs(15, 0.46)));

  // Gap junctions: a plaque of channels bridging to a neighbouring cell.
  const toNeighbour = new THREE.Vector3(0.8, -0.04, -0.6).normalize();
  const neighbour = new THREE.Mesh(new THREE.SphereGeometry(R, 48, 32), ctx.neutral({ opacity: 0.1, depthWrite: false }));
  neighbour.position.copy(toNeighbour).multiplyScalar(2 * R + 0.7);
  neighbour.renderOrder = 2;
  ctx.illustrate(neighbour);
  const junctions = ctx.part("junctions", toNeighbour.clone().multiplyScalar(R + 0.4).add(new THREE.Vector3(0, 2.4, 0)));
  const side = new THREE.Vector3().crossVectors(toNeighbour, UP).normalize();
  const lift = new THREE.Vector3().crossVectors(side, toNeighbour).normalize();
  const bridge = [];
  for (let index = 0; index < 19; index++) {
    const ring = index === 0 ? 0 : index < 7 ? 1 : 2;
    const angle = (index * Math.PI * 2) / (ring === 1 ? 6 : 12);
    const offset = side.clone().multiplyScalar(Math.cos(angle) * ring * 0.62).addScaledVector(lift, Math.sin(angle) * ring * 0.62);
    bridge.push({ direction: toNeighbour, position: toNeighbour.clone().multiplyScalar(R + 0.35).add(offset) });
  }
  junctions.add(instanced(new THREE.CylinderGeometry(0.2, 0.2, 1.5, 8), junctions.material({ roughness: 0.45, shade: -0.12 }), bridge));

  // Water: droplets crossing the membrane at three pores.
  const water = ctx.part("water", new THREE.Vector3(-3.0, 9.3, 3.4));
  const dropMaterial = water.material({ roughness: 0.15, shade: 0.25 });
  water.streams = [new THREE.Vector3(-0.3, 0.86, 0.42), new THREE.Vector3(-0.72, 0.42, 0.55), new THREE.Vector3(-0.1, 0.62, -0.78)].map((direction) => {
    direction.normalize();
    const drops = Array.from({ length: 5 }, () => new THREE.Mesh(DROP, dropMaterial));
    drops.forEach((drop) => water.add(drop));
    return { direction, drops };
  });

  // Injury and repair: a wound ring on the membrane with a few escaping ions.
  const woundAt = new THREE.Vector3(-0.42, -0.5, 0.76).normalize();
  const wound = ctx.part("wound", woundAt.clone().multiplyScalar(R + 1.2));
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.95, 0.1, 8, 28), wound.material({ shade: -0.2 }));
  ring.position.copy(woundAt).multiplyScalar(R + 0.05);
  ring.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), woundAt));
  wound.add(ring);
  wound.add(
    instanced(
      new THREE.SphereGeometry(0.13, 8, 6),
      wound.material({ shade: 0.1 }),
      [0.5, 1.1, 1.8, 2.5].map((distance, index) => ({
        position: woundAt.clone().multiplyScalar(R + distance).addScaledVector(side, (index % 2 ? 0.25 : -0.2) * distance * 0.4),
      }))
    )
  );

  // Division: a dashed belt where the cell is cut in two, on the schedule an experiment sets.
  const furrow = ctx.part("furrow", new THREE.Vector3(-9.2, -2.6, -3.2));
  const belt = new THREE.Group();
  const dashMaterial = furrow.material({ clip: true, shade: -0.28 });
  for (let index = 0; index < 44; index++) {
    const dash = new THREE.Mesh(new THREE.TorusGeometry(R + 0.3, 0.13, 8, 6, 0.085), dashMaterial);
    dash.rotation.z = (index / 44) * Math.PI * 2;
    belt.add(dash);
  }
  belt.rotation.set(Math.PI / 2 - 0.28, 0, 0.2);
  furrow.add(belt);

  // Nucleus: regulatory circuits today; gene regulation coupled to tissue is a planned cage around it.
  const nucleus = ctx.part("nucleus", NUCLEUS.clone().add(new THREE.Vector3(0.4, 3.3, 0)));
  const core = new THREE.Mesh(new THREE.SphereGeometry(2.7, 48, 32), nucleus.material({ roughness: 0.55, shade: 0.08 }));
  core.position.copy(NUCLEUS);
  const nucleolus = new THREE.Mesh(new THREE.SphereGeometry(1.0, 24, 16), nucleus.material({ shade: -0.25 }));
  nucleolus.position.copy(NUCLEUS).add(new THREE.Vector3(1.45, 1.2, 1.55));
  nucleus.add(core, nucleolus);

  const genome = ctx.part("genome", NUCLEUS.clone().add(new THREE.Vector3(3.2, -1.6, 2.6)));
  const cage = new THREE.Mesh(new THREE.IcosahedronGeometry(3.45, 1), genome.material({ wire: true }));
  cage.position.copy(NUCLEUS);
  genome.add(cage);

  // Endoplasmic reticulum: sheets wrapped round the far side of the nucleus; the calcium store.
  const erSide = new THREE.Vector3(-0.55, 0.15, 0.82).normalize();
  const er = ctx.part("er", NUCLEUS.clone().addScaledVector(erSide, 5.6).add(new THREE.Vector3(0, 1.2, 0)));
  const sheetMaterial = er.material({ side: THREE.DoubleSide, roughness: 0.6, shade: 0.34 });
  [3.45, 3.95, 4.45, 4.95].forEach((radius, index) => {
    const sheet = new THREE.Mesh(new THREE.SphereGeometry(radius, 40, 14, index * 0.5, 2.5, 0.18, 0.72), sheetMaterial);
    sheet.position.copy(NUCLEUS);
    sheet.quaternion.copy(along(erSide)).multiply(new THREE.Quaternion().setFromAxisAngle(UP, 1.1 + index * 0.35));
    er.add(sheet);
  });

  // Golgi and trafficking: planned, so only sketched.
  const golgiAt = new THREE.Vector3(6.6, 2.4, 1.2);
  const golgi = ctx.part("golgi", golgiAt.clone().add(new THREE.Vector3(0.4, 1.9, 0.4)));
  const golgiMaterial = golgi.material({ wire: true });
  for (let index = 0; index < 5; index++) {
    const cisterna = new THREE.Mesh(new THREE.TorusGeometry(1.25 + index * 0.13, 0.15, 5, 16, 2.3), golgiMaterial);
    cisterna.position.copy(golgiAt).add(new THREE.Vector3(0, (index - 2) * 0.36, 0));
    cisterna.rotation.set(Math.PI / 2, 0, 0.5);
    golgi.add(cisterna);
  }
  for (const offset of [[1.7, 0.5, 0.9], [2.1, -0.2, 0.2], [1.5, -0.7, 1.4]]) {
    const vesicle = new THREE.Mesh(new THREE.IcosahedronGeometry(0.24, 1), golgiMaterial);
    vesicle.position.copy(golgiAt).add(new THREE.Vector3(...offset));
    golgi.add(vesicle);
  }

  // Mitochondria, and the fuel they are drawn with.
  const mitochondria = ctx.part("mitochondria", new THREE.Vector3(6.2, 2.3, 5.6));
  const mitoMaterial = mitochondria.material({ roughness: 0.5, shade: -0.22 });
  const mitoSpots = [
    { at: new THREE.Vector3(1.2, 5.7, 1.6), turn: new THREE.Euler(0.4, 0.3, 1.1) },
    { at: new THREE.Vector3(3.4, 6.6, 0.9), turn: new THREE.Euler(1.2, 0.2, 0.3) },
    { at: new THREE.Vector3(6.2, 1.1, 5.4), turn: new THREE.Euler(0.2, 1.0, 1.4) },
  ];
  for (const spot of mitoSpots) {
    const body = new THREE.Group();
    body.add(new THREE.Mesh(new THREE.CapsuleGeometry(0.62, 1.7, 8, 20), mitoMaterial));
    for (const y of [-0.55, 0, 0.55]) {
      const band = new THREE.Mesh(new THREE.TorusGeometry(0.64, 0.045, 6, 24), mitoMaterial);
      band.rotation.x = Math.PI / 2;
      band.position.y = y;
      body.add(band);
    }
    body.position.copy(spot.at);
    body.rotation.copy(spot.turn);
    mitochondria.add(body);
  }
  const fuel = ctx.part("atp", new THREE.Vector3(2.6, 8.2, 1.0));
  const sparks = [];
  for (const spot of mitoSpots.slice(0, 2)) {
    for (let index = 0; index < 9; index++) {
      const offset = unit(random).multiplyScalar(1.1 + random() * 0.9);
      const point = spot.at.clone().add(offset);
      if (point.x > 0.2 && point.y > 0.2 && point.z > 0.2 && point.length() < 9) sparks.push({ position: point, scale: 0.8 + random() * 0.6 });
    }
  }
  fuel.add(instanced(new THREE.OctahedronGeometry(0.17), fuel.material({ shade: 0.5, emissive: 0.3 }), sparks));

  // Protein cage: assembled from folded subunits; drawn whole with three free subunits.
  const cageAt = new THREE.Vector3(4.3, 6.1, 3.9);
  const assembly = ctx.part("cage", cageAt.clone().add(new THREE.Vector3(0, 1.5, 0)));
  const shellCage = new THREE.Mesh(new THREE.DodecahedronGeometry(0.95), assembly.material({ flat: true, roughness: 0.5 }));
  shellCage.position.copy(cageAt);
  assembly.spin = shellCage;
  assembly.add(shellCage);
  for (const offset of [[1.5, 0.3, 0.2], [0.9, -0.9, 1.0], [-0.4, 0.5, 1.5]]) {
    const subunit = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.09, 5), assembly.material({ flat: true, shade: 0.15 }));
    subunit.position.copy(cageAt).add(new THREE.Vector3(...offset));
    subunit.rotation.set(offset[0], offset[1], offset[2]);
    assembly.add(subunit);
  }

  // Larger molecular machines: a goal, so sketched. Stacked rings, like a proteasome.
  const machineAt = new THREE.Vector3(2.2, 7.4, 4.5);
  const machine = ctx.part("machine", machineAt.clone().add(new THREE.Vector3(-0.2, 1.5, 0.3)));
  const machineMaterial = machine.material({ wire: true });
  for (let index = 0; index < 4; index++) {
    const stack = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.2, 5, 10), machineMaterial);
    stack.position.copy(machineAt).add(new THREE.Vector3(0, (index - 1.5) * 0.4, 0));
    stack.rotation.x = Math.PI / 2;
    machine.add(stack);
  }

  // Secreted signals leave the cell and spread outside it.
  const secretion = ctx.part("secretion", new THREE.Vector3(9.6, 9.0, -2.4));
  const exit = new THREE.Vector3(0.78, 0.6, -0.18).normalize();
  const drift = new THREE.Vector3(0.25, 0.5, -0.4);
  secretion.path = (t) => exit.clone().multiplyScalar(R + 0.3 + t * 5.5).addScaledVector(drift, t * t * 3);
  const signalMaterial = secretion.material({ shade: 0.1, roughness: 0.3 });
  secretion.beads = Array.from({ length: 9 }, () => new THREE.Mesh(BEAD, signalMaterial));
  secretion.beads.forEach((bead) => secretion.add(bead));

  // The space between cells: ions in the fluid around the cell.
  const outside = ctx.part("extracellular", new THREE.Vector3(-11.8, 8.2, -1.0));
  const view = new THREE.Vector3(0.57, 0.54, 0.62);
  const ions = [];
  let guard = 0;
  while (ions.length < 64 && guard++ < 6000) {
    const direction = unit(random);
    if (Math.abs(direction.dot(view)) > 0.5) continue; // keep the view of the cell clear
    const point = direction.multiplyScalar(R + 1.6 + random() * 5.5);
    if (point.distanceTo(neighbour.position) < R + 1) continue;
    ions.push({ position: point, scale: 0.6 + random() * 0.6 });
  }
  outside.add(instanced(new THREE.SphereGeometry(0.15, 8, 6), outside.material({ opacity: 0.85, shade: 0.1 }), ions));
}

const NUCLEUS = new THREE.Vector3(2.9, 2.5, 2.9);
const DROP = new THREE.SphereGeometry(0.19, 12, 8);
const BEAD = new THREE.SphereGeometry(0.2, 12, 8);

// ------------------------------------------------------------------ molecules

/** The membrane seen close: lipids, one channel and one pump. Illustration of modelled populations. */
export function buildMolecules(ctx) {
  const centre = MOLECULE_PATCH;
  const outward = centre.clone().normalize();
  const tangent = new THREE.Vector3(-outward.y, outward.x, 0).normalize();
  const membrane = ctx.part("membrane");
  const heads = [];
  for (let index = -15; index <= 15; index++) {
    if (Math.abs(index - 4) < 2 || Math.abs(index + 6) < 2) continue; // room for the channel and the pump
    for (const layer of [-0.33, 0.33]) {
      heads.push({ position: centre.clone().addScaledVector(tangent, index * 0.15).addScaledVector(outward, layer), scale: 1 });
    }
  }
  membrane.add(instanced(new THREE.SphereGeometry(0.07, 10, 8), membrane.material({ shade: -0.15, roughness: 0.4 }), heads));
  const tails = [];
  for (const head of heads) {
    const inner = head.position.clone().addScaledVector(outward, -Math.sign(head.position.clone().sub(centre).dot(outward)) * 0.27);
    tails.push(head.position.x, head.position.y, head.position.z, inner.x, inner.y, inner.z);
  }
  const tailGeometry = new THREE.BufferGeometry();
  tailGeometry.setAttribute("position", new THREE.Float32BufferAttribute(tails, 3));
  ctx.illustrate(new THREE.LineSegments(tailGeometry, ctx.neutralLine({ opacity: 0.7, colour: "ghost" })));

  const channel = ctx.part("channels");
  const channelAt = centre.clone().addScaledVector(tangent, 0.6);
  for (const offset of [-0.13, 0.13]) {
    const wall = new THREE.Mesh(new THREE.CapsuleGeometry(0.09, 0.62, 6, 10), channel.material({ shade: -0.1, roughness: 0.4 }));
    wall.position.copy(channelAt).addScaledVector(tangent, offset);
    wall.quaternion.copy(along(outward));
    channel.add(wall);
  }
  channel.ions = Array.from({ length: 5 }, () => new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), channel.material({ shade: 0.35, emissive: 0.2 })));
  channel.ions.forEach((ion) => channel.add(ion));
  channel.path = (t) => channelAt.clone().addScaledVector(outward, 0.85 - t * 1.7);

  const pump = ctx.part("pumps");
  const pumpAt = centre.clone().addScaledVector(tangent, -0.9);
  const lobeMaterial = pump.material({ shade: 0.12, roughness: 0.4 });
  for (const [shift, size, lean] of [[0.12, 0.2, 0.1], [-0.12, 0.17, -0.12], [0, 0.14, 0.42]]) {
    const lobe = new THREE.Mesh(new THREE.SphereGeometry(size, 16, 12), lobeMaterial);
    lobe.position.copy(pumpAt).addScaledVector(tangent, shift).addScaledVector(outward, lean);
    lobe.scale.set(1, 1.5, 1);
    lobe.quaternion.copy(along(outward));
    pump.add(lobe);
  }
  return { centre, outward };
}

export const MOLECULE_PATCH = new THREE.Vector3(Math.cos(0.42), Math.sin(0.42), 0).multiplyScalar(R);

// ------------------------------------------------------------------ tissue

export const HEX = { radius: 10.6, height: 13, rings: 6 };

/** Axial coordinates of a hexagonal sheet: 127 cells for six rings. */
export function sheetCells(rings = HEX.rings) {
  const cells = [];
  for (let q = -rings; q <= rings; q++) {
    for (let r = Math.max(-rings, -q - rings); r <= Math.min(rings, -q + rings); r++) cells.push({ q, r });
  }
  return cells;
}

export const hexCentre = ({ q, r }) => new THREE.Vector3(HEX.radius * Math.sqrt(3) * (q + r / 2), 0, HEX.radius * 1.5 * r);

export function buildTissue(ctx) {
  const prism = new THREE.CylinderGeometry(HEX.radius * 0.955, HEX.radius * 0.955, HEX.height, 6);
  const cells = sheetCells();
  const leaving = { q: 3, r: -1 }, arriving = { q: -2, r: 3 };
  const same = (a, b) => a.q === b.q && a.r === b.r;
  const inPatch = (cell) => cell.q + cell.r / 2 < -2.4 && cell.r < 0; // the mechanics patch
  const plain = cells.filter((cell) => !same(cell, leaving) && !same(cell, arriving) && !inPatch(cell));

  const sheet = ctx.part("sheet", new THREE.Vector3(40, HEX.height / 2 + 6, -58));
  const body = instanced(prism, sheet.material({ roughness: 0.6 }), plain.map((cell) => ({ position: hexCentre(cell) })));
  const tone = seeded(11), shadeOf = new THREE.Color();
  plain.forEach((_, index) => body.setColorAt(index, shadeOf.setScalar(0.9 + tone() * 0.18)));
  body.instanceColor.needsUpdate = true;
  sheet.add(body);
  // The cell this lens opens on, marked so the zoom out keeps its place.
  const marker = new THREE.Mesh(new THREE.TorusGeometry(HEX.radius * 0.8, 0.5, 8, 6), ctx.neutral({ opacity: 0.9, colour: "fg" }));
  marker.rotation.set(Math.PI / 2, 0, Math.PI / 6);
  marker.position.y = HEX.height / 2 + 0.4;
  ctx.illustrate(marker);
  // Lines between neighbours: the junction network that couples the sheet.
  const links = [];
  for (const cell of cells) {
    for (const [dq, dr] of [[1, 0], [0, 1], [-1, 1]]) {
      const other = { q: cell.q + dq, r: cell.r + dr };
      if (!cells.some((item) => same(item, other))) continue;
      const a = hexCentre(cell), b = hexCentre(other);
      const y = HEX.height / 2 + 0.3;
      links.push(a.x * 0.6 + b.x * 0.4, y, a.z * 0.6 + b.z * 0.4, a.x * 0.4 + b.x * 0.6, y, a.z * 0.4 + b.z * 0.6);
    }
  }
  const linkGeometry = new THREE.BufferGeometry();
  linkGeometry.setAttribute("position", new THREE.Float32BufferAttribute(links, 3));
  ctx.illustrate(new THREE.LineSegments(linkGeometry, ctx.neutralLine({ opacity: 0.55, colour: "fg" })));

  // Replacement: one cell lifted out, one newcomer coming in.
  const replacement = ctx.part("replacement", hexCentre(leaving).add(new THREE.Vector3(0, HEX.height * 2.1, 0)));
  const out = new THREE.Mesh(prism, replacement.material({ opacity: 0.5, depthWrite: false }));
  out.position.copy(hexCentre(leaving)).y = HEX.height * 1.25;
  const incoming = new THREE.Mesh(prism, replacement.material({ shade: 0.22 }));
  incoming.position.copy(hexCentre(arriving)).y = HEX.height * 0.55;
  replacement.add(out, incoming);
  for (const cell of [leaving, arriving]) {
    const centre = hexCentre(cell);
    const guide = new THREE.BufferGeometry().setFromPoints([centre.clone().setY(-HEX.height / 2), centre.clone().setY(HEX.height * 2.4)]);
    const line = new THREE.Line(guide, ctx.neutralLine({ opacity: 0.6, colour: "fg", dashed: true }));
    line.computeLineDistances();
    ctx.illustrate(line);
  }

  // Mechanics: a patch drawn as its edges and vertices, the way the vertex model sees it.
  const patch = cells.filter(inPatch);
  const centreOfPatch = patch.reduce((sum, cell) => sum.add(hexCentre(cell)), new THREE.Vector3()).multiplyScalar(1 / patch.length);
  const mechanics = ctx.part("mechanics", centreOfPatch.clone().add(new THREE.Vector3(-8, HEX.height / 2 + 7, -10)));
  mechanics.add(instanced(prism, mechanics.material({ opacity: 0.32, depthWrite: false }), patch.map((cell) => ({ position: hexCentre(cell) }))));
  const edgeMaterial = mechanics.material({ shade: -0.3 });
  const seen = new Set();
  const corner = (cell, index) => {
    const angle = (Math.PI / 3) * index + Math.PI / 6;
    return hexCentre(cell).add(new THREE.Vector3(Math.cos(angle) * HEX.radius, HEX.height / 2 + 0.2, Math.sin(angle) * HEX.radius));
  };
  for (const cell of patch) {
    for (let index = 0; index < 6; index++) {
      const a = corner(cell, index), b = corner(cell, (index + 1) % 6);
      const key = [a, b].map((point) => `${point.x.toFixed(1)},${point.z.toFixed(1)}`).sort().join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      const edge = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, a.distanceTo(b), 6), edgeMaterial);
      edge.position.copy(a).add(b).multiplyScalar(0.5);
      edge.quaternion.copy(along(b.clone().sub(a)));
      mechanics.add(edge);
      const knot = new THREE.Mesh(new THREE.SphereGeometry(0.85, 10, 8), edgeMaterial);
      knot.position.copy(a);
      mechanics.add(knot);
    }
  }
  return { extent: HEX.radius * Math.sqrt(3) * (HEX.rings * 2 + 1) };
}

// ------------------------------------------------------------------ larger scales (placeholders)

export const ORGAN = { radius: 3200, centre: new THREE.Vector3(0, -3200, 0) };
export const BODY = { length: 64000, centre: new THREE.Vector3(15000, -3200, 0) };

/** The organ: planned, so a wire sketch. The sheet above sits on its surface. */
export function buildOrgan(ctx) {
  const organ = ctx.scale("scale.organ", ORGAN.centre.clone().add(new THREE.Vector3(-ORGAN.radius * 0.95, ORGAN.radius * 0.78, 0)));
  const geometry = new THREE.IcosahedronGeometry(ORGAN.radius, 4);
  const position = geometry.attributes.position, point = new THREE.Vector3();
  for (let index = 0; index < position.count; index++) {
    point.fromBufferAttribute(position, index).normalize();
    // A lobed, slightly bean-like body.
    const bulge = 1 + 0.16 * Math.sin(point.x * 2.6 + 0.5) * Math.cos(point.z * 2.1) + 0.1 * Math.sin(point.y * 3.3);
    const squash = point.y > 0.86 ? 1 - (point.y - 0.86) * 1.1 : 1; // flattened where the sheet sits
    point.multiplyScalar(ORGAN.radius * bulge * squash);
    position.setXYZ(index, point.x * 1.18, point.y * 0.92, point.z * 0.95);
  }
  geometry.computeVertexNormals();
  const body = new THREE.Mesh(geometry, organ.material({ wire: true }));
  body.position.copy(ORGAN.centre);
  organ.add(body);
  const patch = new THREE.Mesh(new THREE.RingGeometry(170, 230, 40), ctx.neutral({ opacity: 0.9, colour: "fg", side: THREE.DoubleSide }));
  patch.rotation.x = -Math.PI / 2;
  patch.position.y = 20;
  ctx.illustrate(patch, "organ");
}

/** The whole organism: a long-term goal. A tadpole-like outline, since the frog embryo is in the plan. */
export function buildOrganism(ctx) {
  const organism = ctx.scale("scale.organism", BODY.centre.clone().add(new THREE.Vector3(-BODY.length * 0.2, 13500, 0)));
  const half = BODY.length / 2;
  const profile = [];
  for (let index = 0; index <= 44; index++) {
    const t = index / 44; // 0 at the head, 1 at the tail tip
    const s = (t - 0.45) / 0.55;
    const radius = t < 0.45 ? 10500 * Math.pow(Math.sin((Math.PI * t) / 0.9), 0.62) : 10500 * (0.05 + 0.95 * Math.pow(1 - s, 1.7));
    profile.push(new THREE.Vector2(Math.max(1, radius), -half + t * BODY.length));
  }
  const body = new THREE.Mesh(new THREE.LatheGeometry(profile, 26), organism.material({ wire: true }));
  body.rotation.z = -Math.PI / 2;
  body.scale.set(1, 1, 0.72);
  body.position.copy(BODY.centre);
  organism.add(body);
  const spot = new THREE.Mesh(new THREE.SphereGeometry(ORGAN.radius * 1.1, 20, 14), ctx.neutral({ opacity: 0.85, colour: "fg" }));
  spot.position.copy(ORGAN.centre);
  ctx.illustrate(spot, "organism");
}

export { glyphSprite };
