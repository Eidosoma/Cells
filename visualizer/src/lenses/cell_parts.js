// Geometry for the cell lens. Every shape built here is either bound to a capability
// from the scene file (through ctx.part) or is neutral illustration (ctx.neutral).
// Nothing is drawn that looks like a capability without being one.
//
// Units: 1 is one micrometre. The cell is a generic animal cell about 20 µm across.
// It is drawn as one cell of a layer: the sheet stands for skin-like tissue, a single
// layer of cells, and the cell's neighbours lie round it as scenery. The cell is round
// because the picture chose so: the engine gives a cell a volume and a membrane area,
// not a shape.
// Two size modes share one layout:
//   schematic  parts enlarged and few, so each can be seen (like a textbook cutaway);
//   real       sizes and numbers nearer a real cell; what is too small to see at this
//              zoom is drawn as dots, and appears as shapes when the camera comes close.

import * as THREE from "../three.js";
import { glyphSprite } from "../core/materials.js";

export const R = 10; // the cell's radius
export const CUT = 1.6; // the cell is opened by one flat cut at this height
export const RIM = Math.sqrt(R * R - CUT * CUT); // radius of the cut edge
export const CUT_PLANES = [new THREE.Plane(new THREE.Vector3(0, -1, 0), CUT)];
export const inCut = (point) => point.y > CUT + 0.01;
export const NM = 0.001; // one nanometre

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
const radial = (angle) => new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
const tangent = (angle) => new THREE.Vector3(-Math.sin(angle), 0, Math.cos(angle));
const onRim = (angle, radius = RIM, y = CUT) => new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius);
const turnY = (angle) => new THREE.Quaternion().setFromAxisAngle(UP, angle);

/** Many copies of one shape, each at a position, turned by a quaternion or along a direction. */
function instanced(geometry, material, placements) {
  const mesh = new THREE.InstancedMesh(geometry, material, placements.length);
  const matrix = new THREE.Matrix4(), scale = new THREE.Vector3(), none = new THREE.Quaternion();
  placements.forEach((placement, index) => {
    scale.setScalar(placement.scale ?? 1);
    matrix.compose(placement.position, placement.turn ?? (placement.direction ? along(placement.direction) : none), scale);
    mesh.setMatrixAt(index, matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

/** Dots: how things too small to draw as shapes are shown. */
function dots(points, material) {
  const geometry = new THREE.BufferGeometry();
  const flat = new Float32Array(points.length * 3);
  points.forEach((point, index) => point.toArray(flat, index * 3));
  geometry.setAttribute("position", new THREE.BufferAttribute(flat, 3));
  return new THREE.Points(geometry, material);
}

/** A flat ring-shaped arc standing as a wall: radius, arc length, thickness and height. */
function arcWall(radius, start, span, thickness, height) {
  const geometry = new THREE.TorusGeometry(radius, thickness / 2, 8, Math.max(24, Math.round(span * 26)), span);
  geometry.scale(1, 1, height / thickness);
  const mesh = new THREE.Mesh(geometry);
  // Lay the arc flat (its plane becomes horizontal), then turn it to its start angle.
  mesh.quaternion.copy(turnY(-start)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2));
  return mesh;
}

// ------------------------------------------------------------------ layout shared by both modes

// Where things sit on the cut edge, as angles round the rim.
const SPOT = {
  channels: [0.2, 1.3, 2.1, 3.45, 4.5, 5.25],
  pumps: [1.02, 2.55, 4.95],
  junction: 5.9,
  water: [3.0, 3.9],
  wound: 1.72,
  secretion: 0.62,
  furrow: 2.32,
  charges: [2.78, 3.25, 4.15, 4.72],
};
// The cell's neighbours in the layer, as turns round the cell from the junction: six, a sixth of a turn apart.
const NEIGHBOUR_TURNS = [0, 1, 2, 3, 4, 5].map((step) => (step * Math.PI) / 3);
const GAP_TURN = (-5 * Math.PI) / 6; // midway between two neighbours, on the side the space between cells is named
const NUCLEUS = new THREE.Vector3(2.6, CUT - 0.3, -2.2);
const ER_FACING = 2.42; // the side of the nucleus the ER wraps, as an angle
const GOLGI = new THREE.Vector3(-4.9, CUT + 0.15, 4.3);
const MACHINE = new THREE.Vector3(-7.2, CUT + 0.9, -1.0);
const MITO_AT_SURFACE = [[-4.7, -4.5, 0.5], [6.9, 0.9, 1.45], [1.9, 6.1, -0.35]]; // x, z, turn
const CAGES_AT_SURFACE = [new THREE.Vector3(4.9, CUT + 0.55, 3.9), new THREE.Vector3(-1.4, CUT + 0.5, -7.0)];

const STYLE = {
  schematic: {
    id: "schematic",
    shellOpacity: 0.44, band: 0.5, beads: true,
    nucleusRadius: 3.1, nucleolus: 1.05,
    er: { layers: 4, first: 3.95, gap: 0.72, thickness: 0.22, height: 1.35, span: 3.0, shrink: 0.42 },
    golgi: { inner: 1.5, gap: 0.36, count: 5, half: 0.14, tube: 0.035, span: 1.7 },
    drop: 0.19, bead: 0.2, wound: 0.5, dash: 0.12, charge: 0.8, neighbourGap: 0.9,
  },
  real: {
    id: "real",
    shellOpacity: 0.3, band: 0.06, beads: false,
    nucleusRadius: 3.0, nucleolus: 0.8,
    er: { layers: 8, first: 3.3, gap: 0.3, thickness: 0.07, height: 0.6, span: 3.3, shrink: 0.3 },
    golgi: { inner: 0.75, gap: 0.14, count: 6, half: 0.05, tube: 0.014, span: 1.5 },
    drop: 0.055, bead: 0.06, wound: 0.25, dash: 0.05, charge: 0.45, neighbourGap: 0.04,
  },
};

/**
 * Builds one cell in the given size mode. Returns handles the lens animates, the
 * points the input check clicks, and where the close-up of the membrane is.
 */
export function buildCell(ctx, studsCtx, mode) {
  const style = STYLE[mode];
  const real = mode === "real";
  const random = seeded(real ? 23 : 7);
  const handles = { cages: [] };
  const inCytoplasm = (point, clear = 0.6) =>
    point.length() < 8.9 && point.y < CUT + 0.2 && point.distanceTo(NUCLEUS) > style.nucleusRadius + clear;
  const scatter = (count, test = inCytoplasm) => {
    const found = [];
    let guard = 0;
    while (found.length < count && guard++ < count * 60) {
      const point = unit(random).multiplyScalar(8.9 * Math.cbrt(random()));
      if (test(point)) found.push(point);
    }
    return found;
  };
  const onSkin = (count, minGap = 0) => {
    // Random spots on the outer membrane, below the cut and clear of the neighbour.
    const found = [];
    let guard = 0;
    while (found.length < count && guard++ < count * 80) {
      const direction = unit(random);
      if (direction.y * R > CUT - 0.9) continue;
      if (direction.angleTo(radial(SPOT.junction)) < 0.28) continue;
      if (minGap && found.some((other) => other.direction.angleTo(direction) < minGap)) continue;
      found.push({ direction, position: direction.clone().multiplyScalar(R) });
    }
    return found;
  };

  // ---------------------------------------------------------------- membrane
  const membrane = ctx.part("membrane", onRim(4.42, RIM + 0.9, CUT + 0.3));
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(R, 96, 64),
    membrane.material({ hue: "bioMembrane", opacity: style.shellOpacity, side: THREE.DoubleSide, clip: true, roughness: 0.25, depthWrite: false, rim: 0.5, alphaRim: 0.5 })
  );
  shell.userData.pickFilter = (hit) => !inCut(hit.point);
  shell.renderOrder = 6; // after what is inside it, so it tints them like glass
  membrane.add(shell);
  // The cut edge: the membrane seen in section. Schematic: a thick band with lipid beads.
  const edgeLine = (radius = RIM) => {
    const circle = [];
    for (let index = 0; index < 256; index++) circle.push(onRim((index / 256) * Math.PI * 2, radius, CUT + 0.0002));
    return new THREE.BufferGeometry().setFromPoints(circle);
  };
  if (real) {
    membrane.add(new THREE.LineLoop(edgeLine(), membrane.lineMaterial({ hue: "bioMembrane", opacity: 1 })));
  } else {
    const band = new THREE.Mesh(
      new THREE.RingGeometry(RIM - style.band * 0.72, RIM + style.band * 0.28, 160),
      membrane.material({ hue: "bioMembrane", shade: -0.22, side: THREE.DoubleSide, roughness: 0.5 })
    );
    band.rotation.x = -Math.PI / 2;
    band.position.y = CUT + 0.004;
    membrane.add(band);
  }
  const taken = [...SPOT.channels, ...SPOT.pumps, SPOT.wound];
  if (style.beads) {
    const heads = [];
    const count = Math.round((2 * Math.PI * RIM) / 0.43);
    for (let index = 0; index < count; index++) {
      const angle = (index / count) * Math.PI * 2;
      if (taken.some((spot) => Math.abs(Math.atan2(Math.sin(angle - spot), Math.cos(angle - spot))) < 0.075)) continue;
      heads.push({ position: onRim(angle, RIM + 0.15, CUT + 0.06) }, { position: onRim(angle + 0.02, RIM - 0.33, CUT + 0.06) });
    }
    membrane.add(instanced(new THREE.SphereGeometry(0.2, 12, 9), membrane.material({ hue: "bioMembrane", shade: 0.22, roughness: 0.3 }), heads));
  }
  // Charge across the membrane: plus outside, minus inside.
  for (const angle of SPOT.charges) {
    studsCtx.sprite(membrane, "+", onRim(angle, RIM + (real ? 0.5 : 1.05), CUT + 0.3), style.charge);
    studsCtx.sprite(membrane, "−", onRim(angle, RIM - (real ? 0.5 : 1.15), CUT + 0.3), style.charge);
  }

  // ---------------------------------------------------------------- channels and pumps
  const channels = ctx.part("channels", onRim(SPOT.channels[3], RIM + 0.5, CUT + 0.5));
  const pumps = ctx.part("pumps", onRim(SPOT.pumps[1], RIM + 0.5, CUT + 0.5));
  if (!real) {
    // Set in the cut edge: each channel is two walls with a pore between; each pump a lobed block.
    const wall = new THREE.CapsuleGeometry(0.17, 0.62, 6, 12).rotateZ(Math.PI / 2); // long axis along x
    const walls = [];
    for (const angle of SPOT.channels) {
      for (const offset of [-0.25, 0.25]) {
        walls.push({ position: onRim(angle, RIM - 0.1, CUT + 0.07).addScaledVector(tangent(angle), offset), turn: turnY(-angle) });
      }
    }
    channels.add(instanced(wall, channels.material({ hue: "bioProtein", roughness: 0.35 }), walls));
    const lobes = pumps.material({ hue: "bioPump", roughness: 0.35 });
    for (const angle of SPOT.pumps) {
      const outer = new THREE.Mesh(new THREE.SphereGeometry(0.46, 18, 14), lobes);
      outer.position.copy(onRim(angle, RIM - 0.05, CUT + 0.08));
      outer.scale.set(1, 0.85, 1);
      const inner = new THREE.Mesh(new THREE.SphereGeometry(0.32, 16, 12), lobes);
      inner.position.copy(onRim(angle, RIM - 0.62, CUT));
      pumps.add(outer, inner);
    }
    // And over the rest of the membrane: pores and low domes.
    const exteriorChannels = studsCtx.part("channels");
    exteriorChannels.add(
      instanced(new THREE.TorusGeometry(0.3, 0.1, 8, 18).rotateX(Math.PI / 2), exteriorChannels.material({ hue: "bioProtein", roughness: 0.4 }), onSkin(30, 0.22))
    );
    const exteriorPumps = studsCtx.part("pumps");
    exteriorPumps.add(
      instanced(new THREE.SphereGeometry(0.44, 16, 12).scale(1, 0.6, 1), exteriorPumps.material({ hue: "bioPump", roughness: 0.4 }), onSkin(12, 0.4))
    );
  } else {
    // At this scale a channel is about 10 nm across: far too small to see. Thousands of them
    // are drawn as dots; the close-up of the membrane shows them as shapes.
    const dust = studsCtx.part("channels");
    dust.add(dots(onSkin(4200).map((spot) => spot.position), dust.points({ hue: "bioProtein", size: 1.9 })));
    const pumpDust = studsCtx.part("pumps");
    pumpDust.add(dots(onSkin(2400).map((spot) => spot.position), pumpDust.points({ hue: "bioPump", size: 1.9 })));
  }

  // ---------------------------------------------------------------- gap junctions and the neighbours
  // The cell is one of a layer, so its neighbours lie round it in the plane of the cut,
  // six as in a packed sheet. They are scenery: faint glass that cannot be clicked. The one
  // the junction leads to is drawn a little stronger, as before; the others are only a
  // thin outline where the cut passes through them, so nothing outside the membrane is hidden.
  const toward = radial(SPOT.junction);
  const neighbourAt = toward.clone().multiplyScalar(2 * R + style.neighbourGap);
  const neighbours = NEIGHBOUR_TURNS.map((turn) => radial(SPOT.junction + turn).multiplyScalar(2 * R + style.neighbourGap));
  const ball = new THREE.SphereGeometry(R, 64, 40);
  const glass = ctx.neutral({ opacity: 0.035, glass: 0.2, clip: true, side: THREE.DoubleSide });
  const fainter = ctx.neutral({ opacity: 0.014, glass: 0.09, clip: true, side: THREE.DoubleSide });
  const neighbourLine = ctx.neutralLine({ opacity: real ? 0.6 : 0.5 });
  const fainterLine = ctx.neutralLine({ opacity: 0.3 });
  neighbours.forEach((at, index) => {
    const first = index === 0;
    const neighbour = new THREE.Mesh(ball, first ? glass : fainter);
    neighbour.position.copy(at);
    neighbour.renderOrder = 7;
    ctx.illustrate(neighbour);
    if (real || !first) {
      const line = new THREE.LineLoop(edgeLine(), first ? neighbourLine : fainterLine);
      line.position.copy(at);
      ctx.illustrate(line);
    } else {
      const neighbourBand = new THREE.Mesh(new THREE.RingGeometry(RIM - style.band * 0.72, RIM + style.band * 0.28, 120), ctx.neutral({ opacity: 0.3, side: THREE.DoubleSide }));
      neighbourBand.rotation.x = -Math.PI / 2;
      neighbourBand.position.copy(at).setY(CUT + 0.004);
      ctx.illustrate(neighbourBand);
    }
  });
  const junctions = ctx.part("junctions", onRim(SPOT.junction, RIM + 0.6, CUT + 0.6));
  if (!real) {
    const bridge = [];
    for (const drop of [0.02, -0.62]) {
      for (let index = -2; index <= 2; index++) {
        const reach = R + style.neighbourGap / 2 - (R - Math.sqrt(R * R - (CUT + drop) * (CUT + drop))); // half-way between the two membranes at this height
        bridge.push({ position: toward.clone().multiplyScalar(reach).setY(CUT + drop).addScaledVector(tangent(SPOT.junction), index * 0.46), direction: toward });
      }
    }
    junctions.add(instanced(new THREE.CylinderGeometry(0.19, 0.19, 1.55, 10), junctions.material({ hue: "bioProtein", shade: -0.08, roughness: 0.35 }), bridge));
  } else {
    // A plaque of some hundreds of channels where the two cells touch.
    const plaque = [];
    const centre = toward.clone().multiplyScalar(R + 0.02).setY(0.2);
    for (let index = 0; index < 700; index++) {
      const r = 0.55 * Math.sqrt(random()), angle = random() * Math.PI * 2;
      plaque.push(centre.clone().addScaledVector(tangent(SPOT.junction), Math.cos(angle) * r).addScaledVector(UP, Math.sin(angle) * r));
    }
    junctions.add(dots(plaque, junctions.points({ hue: "bioProtein", size: 1.9 })));
  }

  // ---------------------------------------------------------------- cytoplasm
  const chemistry = ctx.part("cytoplasm", new THREE.Vector3(-3.9, CUT + 0.15, -7.4));
  const gel = new THREE.Mesh(
    new THREE.CircleGeometry(real ? RIM - 0.003 : RIM - style.band * 0.72, real ? 256 : 96),
    chemistry.material({ hue: "bioCyto", opacity: real ? 0.42 : 0.3, side: THREE.DoubleSide, roughness: 0.12, depthWrite: false, rim: 0 })
  );
  gel.rotation.x = -Math.PI / 2;
  gel.position.y = real ? CUT - 0.0006 : CUT - 0.02;
  gel.renderOrder = 3;
  chemistry.add(gel);
  if (!real) {
    const specks = instanced(new THREE.SphereGeometry(0.09, 8, 6), chemistry.material({ hue: "bioCyto", shade: -0.3 }), scatter(190).map((position) => ({ position, scale: 0.6 + random() * 0.9 })));
    const tone = new THREE.Color();
    for (let index = 0; index < specks.count; index++) specks.setColorAt(index, tone.setHSL(random(), 0.5, 0.72));
    specks.instanceColor.needsUpdate = true;
    chemistry.add(specks);
  } else {
    chemistry.add(dots(scatter(7000), chemistry.points({ hue: "bioCyto", shade: -0.35, size: 1.3, opacity: 0.5 })));
  }
  // Vesicles: scenery, so neutral glass.
  const bubbles = real
    ? scatter(80, (point) => inCytoplasm(point, 0.8)).map((position) => ({ position, scale: 0.12 + random() * 0.22 }))
    : [[-5.9, 1.5], [0.4, 8.0], [7.4, -3.4], [-2.6, -4.4], [4.3, 6.9], [-7.6, -3.6]].map(([x, z]) => ({ position: new THREE.Vector3(x, CUT + 0.05, z), scale: 0.45 + random() * 0.3 }));
  ctx.illustrate(instanced(new THREE.SphereGeometry(1, 20, 14), ctx.neutral({ opacity: 0.14, glass: 0.5 }), bubbles));

  // ---------------------------------------------------------------- nucleus
  const nucleus = ctx.part("nucleus", NUCLEUS.clone().add(new THREE.Vector3(0, style.nucleusRadius + 0.1, 0)));
  const envelope = new THREE.Mesh(new THREE.SphereGeometry(style.nucleusRadius, 56, 40), nucleus.material({ hue: "bioNucleus", opacity: 0.78, roughness: 0.3, rim: 0.55, depthWrite: true }));
  envelope.position.copy(NUCLEUS);
  envelope.renderOrder = 2;
  const nucleolus = new THREE.Mesh(new THREE.SphereGeometry(style.nucleolus, 28, 20), nucleus.material({ hue: "bioNucleus", shade: -0.38, roughness: 0.5 }));
  nucleolus.position.copy(NUCLEUS).add(new THREE.Vector3(0.55, 1.15, 0.85));
  nucleus.add(nucleolus, envelope);
  const pores = [];
  while (pores.length < (real ? 1500 : 80)) {
    const direction = unit(random);
    if (real || direction.y > -0.25) pores.push(NUCLEUS.clone().addScaledVector(direction, style.nucleusRadius + 0.01));
  }
  if (real) nucleus.add(dots(pores, nucleus.points({ hue: "bioNucleus", shade: 0.4, size: 1.4, opacity: 0.8 })));
  else nucleus.add(instanced(new THREE.SphereGeometry(0.085, 8, 6), nucleus.material({ hue: "bioNucleus", shade: 0.32 }), pores.map((position) => ({ position }))));

  // Gene regulation coupled to tissue is planned: a sketched network round the nucleus.
  const genome = ctx.part("genome", NUCLEUS.clone().add(new THREE.Vector3(style.nucleusRadius + 0.3, 1.5, 1.9)));
  const net = new THREE.IcosahedronGeometry(style.nucleusRadius + 0.6, 1);
  const cage = new THREE.LineSegments(new THREE.EdgesGeometry(net, 1), genome.lineMaterial({ opacity: 0.75 }));
  cage.position.copy(NUCLEUS);
  const knots = [], seen = new Set(), corner = new THREE.Vector3();
  for (let index = 0; index < net.attributes.position.count; index++) {
    corner.fromBufferAttribute(net.attributes.position, index);
    const key = corner.toArray().map((value) => value.toFixed(2)).join();
    if (!seen.has(key)) {
      seen.add(key);
      knots.push({ position: corner.clone().add(NUCLEUS) });
    }
  }
  const body = new THREE.Mesh(net, genome.proxyMaterial());
  body.position.copy(NUCLEUS);
  genome.add(cage, body, instanced(new THREE.SphereGeometry(0.1, 8, 6), genome.material({ line: true }), knots));

  // ---------------------------------------------------------------- endoplasmic reticulum, the calcium store
  const er = ctx.part("er", NUCLEUS.clone().addScaledVector(radial(ER_FACING), style.er.first + style.er.gap * 1.5).setY(CUT + style.er.height * 0.45));
  const sheet = er.material({ hue: "bioEr", roughness: 0.4, side: THREE.DoubleSide });
  const studs = [];
  for (let layer = 0; layer < style.er.layers; layer++) {
    const radius = style.er.first + layer * style.er.gap;
    const span = Math.max(0.9, style.er.span - layer * style.er.shrink);
    const start = ER_FACING - span / 2 + (layer % 2 ? 0.12 : -0.08);
    const wall = arcWall(radius, start, span, style.er.thickness, style.er.height);
    wall.material = sheet;
    wall.position.copy(NUCLEUS).setY(CUT - style.er.height * 0.12);
    er.add(wall);
    // Ribosomes on the sheets. Protein synthesis is not a capability, so they are scenery: neutral grey.
    const perLayer = real ? Math.round(span * radius * 22) : Math.round(span * radius * 1.7);
    for (let index = 0; index < perLayer; index++) {
      const angle = start + (span * (index + random() * 0.6)) / perLayer;
      const out = (random() < 0.5 ? 1 : -1) * (style.er.thickness / 2 + (real ? 0.012 : 0.07));
      studs.push(NUCLEUS.clone().addScaledVector(radial(angle), radius + out).setY(CUT - style.er.height * 0.12 + (random() - 0.5) * style.er.height * 0.9));
    }
  }
  if (real) {
    ctx.illustrate(dots(studs, ctx.neutralPoints({ size: 1.3, opacity: 0.8 })));
    // The network reaches through the cell as tubules; free ribosomes (scenery) fill the cytosol.
    const tubes = [];
    for (let strand = 0; strand < 70; strand++) {
      const point = NUCLEUS.clone().addScaledVector(unit(random), style.nucleusRadius + 0.4 + random() * 2.5);
      const heading = unit(random);
      for (let step = 0; step < 14; step++) {
        const next = point.clone().addScaledVector(heading.add(unit(random).multiplyScalar(0.55)).normalize(), 0.42);
        if (!inCytoplasm(next, 0.2)) break;
        tubes.push(point.x, point.y, point.z, next.x, next.y, next.z);
        point.copy(next);
      }
    }
    const web = new THREE.BufferGeometry();
    web.setAttribute("position", new THREE.Float32BufferAttribute(tubes, 3));
    er.add(new THREE.LineSegments(web, er.lineMaterial({ hue: "bioEr", opacity: 0.55 })));
    ctx.illustrate(dots(scatter(6000), ctx.neutralPoints({ size: 1.1, opacity: 0.35 })));
  } else {
    ctx.illustrate(instanced(new THREE.SphereGeometry(0.085, 8, 6), ctx.neutral({ opacity: 0.8, depthWrite: true }), studs.map((position) => ({ position }))));
  }

  // ---------------------------------------------------------------- Golgi and trafficking: planned, so sketched as outlines
  const golgi = ctx.part("golgi", GOLGI.clone().add(new THREE.Vector3(0, 0.7, 0)));
  const outline = golgi.material({ line: true });
  const facing = Math.atan2(GOLGI.z - NUCLEUS.z, GOLGI.x - NUCLEUS.x);
  const hub = GOLGI.clone().addScaledVector(radial(facing), -(style.golgi.inner + style.golgi.gap * 2));
  for (let index = 0; index < style.golgi.count; index++) {
    const radius = style.golgi.inner + index * style.golgi.gap;
    const span = style.golgi.span - index * 0.1;
    const points = [];
    for (let step = 0; step <= 14; step++) points.push(hub.clone().addScaledVector(radial(facing - span / 2 + (span * step) / 14), radius + style.golgi.half));
    for (let step = 14; step >= 0; step--) points.push(hub.clone().addScaledVector(radial(facing - span / 2 + (span * step) / 14), radius - style.golgi.half));
    golgi.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, true, "catmullrom", 0.25), 110, style.golgi.tube, 6, true), outline));
  }
  const far = style.golgi.inner + style.golgi.count * style.golgi.gap;
  for (const [turn, reach] of [[-0.5, 1.5], [0.05, 1.8], [0.55, 1.45], [0.2, 2.6]]) {
    const vesicle = new THREE.Mesh(new THREE.TorusGeometry(style.golgi.half * 1.5, style.golgi.tube, 6, 22), outline);
    vesicle.position.copy(hub).addScaledVector(radial(facing + turn), far + reach * style.golgi.gap);
    vesicle.rotation.x = Math.PI / 2;
    golgi.add(vesicle);
  }
  const golgiBody = new THREE.Mesh(new THREE.CylinderGeometry(far * 0.75, far * 0.75, 0.5, 16), golgi.proxyMaterial());
  golgiBody.position.copy(GOLGI);
  golgi.add(golgiBody);

  // ---------------------------------------------------------------- mitochondria and fuel
  const mitochondria = ctx.part("mitochondria", new THREE.Vector3(MITO_AT_SURFACE[1][0], CUT + 0.75, MITO_AT_SURFACE[1][1]));
  const fuel = ctx.part("atp", new THREE.Vector3(-0.9, CUT + 0.55, 7.4));
  if (!real) {
    const outer = mitochondria.material({ hue: "bioMito", clip: true, side: THREE.DoubleSide, roughness: 0.35 });
    const matrix = mitochondria.material({ hue: "bioMito", shade: 0.5, roughness: 0.5 });
    const crista = mitochondria.material({ hue: "bioMito", shade: -0.05, roughness: 0.45 });
    const stadium = new THREE.Shape();
    stadium.absarc(1.0, 0, 0.8, -Math.PI / 2, Math.PI / 2, false);
    stadium.absarc(-1.0, 0, 0.8, Math.PI / 2, (3 * Math.PI) / 2, false);
    for (const [x, z, turn] of MITO_AT_SURFACE) {
      const one = new THREE.Group();
      one.add(new THREE.Mesh(new THREE.CapsuleGeometry(0.95, 2.0, 10, 24).rotateZ(Math.PI / 2), outer));
      const floor = new THREE.Mesh(new THREE.ShapeGeometry(stadium, 16).rotateX(-Math.PI / 2), matrix);
      floor.position.y = 0.1;
      one.add(floor);
      [-1.2, -0.6, 0, 0.6, 1.2].forEach((offset, index) => {
        const fold = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.34, 1.05), crista);
        fold.position.set(offset, 0.03, index % 2 ? 0.27 : -0.27);
        one.add(fold);
      });
      one.position.set(x, CUT - 0.12, z);
      one.rotation.y = turn;
      mitochondria.add(one);
    }
    const whole = mitochondria.material({ hue: "bioMito", roughness: 0.4 });
    const deep = [[-6.0, -3.6, 0.6], [0.6, -5.6, -3.4], [5.0, -4.6, 3.0], [-2.6, -6.2, 4.0], [-3.4, -2.4, -6.4], [6.4, -2.2, -4.6]];
    // Lying roughly level, like the ones at the surface.
    const level = () => radial(random() * Math.PI * 2).setY((random() - 0.5) * 0.5);
    mitochondria.add(instanced(new THREE.CapsuleGeometry(0.8, 1.8, 8, 20), whole, deep.map((xyz) => ({ position: new THREE.Vector3(...xyz), direction: level() }))));
    const sparks = [];
    for (const [x, z] of [...MITO_AT_SURFACE, [-0.9, 7.2]]) {
      for (let index = 0; index < 7; index++) {
        const angle = random() * Math.PI * 2, reach = 1.5 + random() * 0.9;
        const point = new THREE.Vector3(x + Math.cos(angle) * reach * 1.25, CUT + 0.12 + random() * 0.3, z + Math.sin(angle) * reach);
        if (Math.hypot(point.x, point.z) < RIM - 1.1 && point.distanceTo(NUCLEUS) > style.nucleusRadius + 0.6) sparks.push({ position: point, scale: 0.8 + random() * 0.5 });
      }
    }
    fuel.add(instanced(new THREE.SphereGeometry(0.17, 12, 9), fuel.material({ hue: "bioFuel", emissive: 0.22, roughness: 0.3 }), sparks));
  } else {
    // Mitochondria are about 0.6 µm wide and a few µm long; a cell holds hundreds.
    const many = scatter(120, (point) => inCytoplasm(point, 0.7) && point.y < CUT);
    // Each is a clear outer membrane, curved more or less, with the folds of its inner
    // membrane (the cristae) showing through: stacked shelves across the long axis.
    const shapes = [
      { radius: 0.26, length: 1.1, bend: 0 },
      { radius: 0.3, length: 1.8, bend: 0.26 },
      { radius: 0.27, length: 2.7, bend: -0.42 },
    ];
    const curved = ({ radius, length, bend }) => {
      const geometry = new THREE.CapsuleGeometry(radius, length, 8, 18);
      const half = length / 2 + radius, spot = geometry.attributes.position;
      for (let index = 0; index < spot.count; index++) spot.setX(index, spot.getX(index) + bend * (spot.getY(index) / half) ** 2);
      geometry.computeVertexNormals();
      return geometry;
    };
    const outer = mitochondria.material({ hue: "bioMito", shade: 0.1, opacity: 0.3, alphaRim: 0.55, rim: 0.45, clip: true, side: THREE.DoubleSide, roughness: 0.3, depthWrite: false });
    const fold = mitochondria.material({ hue: "bioMito", shade: -0.06, clip: true, roughness: 0.5 });
    const placed = shapes.map(() => []);
    for (const position of many) placed[Math.floor(random() * shapes.length)].push({ position, turn: along(unit(random)), scale: 0.85 + random() * 0.35 });
    const folds = [];
    shapes.forEach((shape, which) => {
      const bodies = instanced(curved(shape), outer, placed[which]);
      bodies.renderOrder = 4; // after the folds, so they show through the membrane
      mitochondria.add(bodies);
      const half = shape.length / 2 + shape.radius;
      const count = Math.max(3, Math.round(shape.length / 0.3));
      for (const one of placed[which]) {
        const base = new THREE.Matrix4().compose(one.position, one.turn, new THREE.Vector3().setScalar(one.scale));
        for (let index = 0; index < count; index++) {
          const y = -shape.length / 2 + (shape.length * (index + 0.5)) / count;
          const side = index % 2 ? 1 : -1; // shelves reach in from alternate sides
          const at = new THREE.Vector3(shape.bend * (y / half) ** 2 + side * 0.16 * shape.radius, y, 0);
          const tilt = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, side * 0.14));
          folds.push(base.clone().multiply(new THREE.Matrix4().compose(at, tilt, new THREE.Vector3(shape.radius * 0.74, 1, shape.radius * 0.82))));
        }
      }
    });
    const shelves = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1, 0.05, 14), fold, folds.length);
    folds.forEach((matrix, index) => shelves.setMatrixAt(index, matrix));
    shelves.instanceMatrix.needsUpdate = true;
    mitochondria.add(shelves);
    mitochondria.anchor.copy(many.reduce((best, point) => (point.y > best.y ? point : best), many[0])).y += 0.5;
    // ATP is a small molecule: shown as a haze, densest beside the mitochondria.
    const haze = [];
    for (let index = 0; index < 4500; index++) {
      const point = many[Math.floor(random() * many.length)].clone().addScaledVector(unit(random), 0.35 + random() * 0.9);
      if (inCytoplasm(point, 0.1)) haze.push(point);
    }
    fuel.add(dots(haze, fuel.points({ hue: "bioFuel", size: 1.3, opacity: 0.55 })));
    fuel.anchor.copy(mitochondria.anchor).add(new THREE.Vector3(1.2, 0, 1.2));
  }

  // ---------------------------------------------------------------- protein cages (assembly) and larger machines (planned)
  const assembly = ctx.part("cage", CAGES_AT_SURFACE[0].clone().add(new THREE.Vector3(0, 1.25, 0)));
  const machine = ctx.part("machine", MACHINE.clone().add(new THREE.Vector3(0, 1.2, 0)));
  if (!real) {
    const corners = new THREE.DodecahedronGeometry(0.78).attributes.position, unique = new Map(), at = new THREE.Vector3();
    for (let index = 0; index < corners.count; index++) {
      at.fromBufferAttribute(corners, index);
      unique.set(at.toArray().map((value) => value.toFixed(2)).join(), at.clone());
    }
    const subunit = assembly.material({ hue: "bioProtein", shade: 0.12, roughness: 0.3 });
    const ball = new THREE.SphereGeometry(0.3, 14, 10);
    for (const centre of [...CAGES_AT_SURFACE, new THREE.Vector3(-5.5, -3.6, -3.0), new THREE.Vector3(3.0, -5.8, 2.0)]) {
      const cluster = instanced(ball, subunit, [...unique.values()].map((position) => ({ position })));
      cluster.position.copy(centre);
      handles.cages.push(cluster);
      assembly.add(cluster);
      // Free subunits beside it: the finite pool the cage is built from.
      assembly.add(instanced(ball, subunit, [0, 1, 2].map(() => ({ position: centre.clone().add(new THREE.Vector3((random() - 0.5) * 3.2, random() * 0.25, (random() - 0.5) * 3.2)) }))));
    }
    const rings = machine.material({ line: true });
    for (let index = 0; index < 4; index++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(index % 3 ? 0.62 : 0.5, 0.035, 6, 30), rings);
      ring.position.copy(MACHINE).add(new THREE.Vector3(0, (index - 1.5) * 0.36, 0));
      ring.rotation.x = Math.PI / 2;
      machine.add(ring);
    }
    const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 1.4, 12), machine.proxyMaterial());
    barrel.position.copy(MACHINE);
    machine.add(barrel);
  } else {
    // A cage is tens of nanometres across: dots at this scale.
    assembly.add(dots(scatter(2200), assembly.points({ hue: "bioProtein", shade: 0.12, size: 1.7, opacity: 0.85 })));
    // Planned machines: a sketched ring marks where their dots would be.
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.7, 0.014, 6, 40), machine.material({ line: true }));
    ring.position.copy(MACHINE).setY(CUT + 0.03);
    ring.rotation.x = Math.PI / 2;
    const spot = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.3, 16), machine.proxyMaterial());
    spot.position.copy(ring.position);
    const few = [];
    for (let index = 0; index < 140; index++) few.push(ring.position.clone().add(new THREE.Vector3((random() - 0.5) * 1.1, (random() - 0.6) * 0.5, (random() - 0.5) * 1.1)));
    machine.add(ring, spot, dots(few, machine.points({ size: 1.6, opacity: 0.8 })));
    machine.anchor.copy(ring.position).y += 0.4;
    assembly.anchor.copy(CAGES_AT_SURFACE[0]).setY(CUT + 0.3);
  }

  // ---------------------------------------------------------------- water, wound, division, secretion, the space outside
  const water = ctx.part("water", onRim(SPOT.water[0], RIM + 1.9, CUT + 0.4));
  const dropMaterial = water.material({ hue: "bioWater", roughness: 0.08, rim: 0.6 });
  const dropShape = new THREE.SphereGeometry(style.drop, 14, 10);
  handles.streams = SPOT.water.map((angle, which) => {
    const drops = Array.from({ length: real ? 9 : 5 }, () => new THREE.Mesh(dropShape, dropMaterial));
    drops.forEach((drop) => water.add(drop));
    return { angle, inward: which === 0, drops, reach: real ? 0.7 : 1.6 };
  });

  const wound = ctx.part("wound", onRim(SPOT.wound, RIM + 1.5, CUT - 0.2));
  const woundAt = onRim(SPOT.wound, Math.sqrt(R * R - (CUT - 0.9) * (CUT - 0.9)) + 0.03, CUT - 0.9);
  const scar = new THREE.Mesh(new THREE.TorusGeometry(style.wound, style.wound * 0.17, 8, 28), wound.material({ hue: "bioWound", roughness: 0.4 }));
  scar.position.copy(woundAt);
  scar.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), woundAt.clone().normalize());
  wound.add(scar);
  wound.add(
    instanced(
      new THREE.SphereGeometry(style.wound * 0.24, 8, 6),
      wound.material({ hue: "bioWound", shade: 0.25 }),
      [0.5, 1.1, 1.8, 2.5].map((reach, index) => ({ position: woundAt.clone().addScaledVector(woundAt.clone().normalize(), reach * style.wound * 2).addScaledVector(tangent(SPOT.wound), (index % 2 ? 0.5 : -0.4) * style.wound) }))
    )
  );

  const furrow = ctx.part("furrow", onRim(SPOT.furrow, RIM + 0.9, CUT + 0.2));
  const belt = new THREE.Group();
  const dash = furrow.material({ hue: "bioMembrane", shade: -0.42, clip: true });
  for (let index = 0; index < 52; index++) {
    const piece = new THREE.Mesh(new THREE.TorusGeometry(R + 0.22, style.dash, 6, 6, 0.07), dash);
    piece.rotation.z = (index / 52) * Math.PI * 2;
    belt.add(piece);
  }
  belt.rotation.y = -SPOT.furrow; // a vertical circle through the two furrow points on the rim
  furrow.add(belt);
  // The same line continues a little way across the cut surface, at both ends.
  const mark = furrow.material({ hue: "bioMembrane", shade: -0.42 });
  for (const side of [0, Math.PI]) {
    for (let step = 0; step < 3; step++) {
      const piece = new THREE.Mesh(new THREE.BoxGeometry(0.5, style.dash, style.dash * 1.6), mark);
      piece.position.copy(onRim(SPOT.furrow + side, RIM - 1.0 - step * 0.95, CUT + 0.05));
      piece.rotation.y = -(SPOT.furrow + side);
      furrow.add(piece);
    }
  }

  const secretion = ctx.part("secretion", onRim(SPOT.secretion, RIM + 4.6, CUT + 2.0));
  const out = radial(SPOT.secretion);
  handles.signalPath = (t) => onRim(SPOT.secretion, RIM + 0.3 + t * 5.5, CUT - 0.1).addScaledVector(UP, t * 0.8 + t * t * 1.6).addScaledVector(tangent(SPOT.secretion), t * t * 1.2);
  const signal = secretion.material({ hue: "bioSignal", roughness: 0.25 });
  handles.signals = Array.from({ length: real ? 24 : 9 }, () => new THREE.Mesh(new THREE.SphereGeometry(style.bead, 12, 9), signal));
  handles.signals.forEach((bead) => secretion.add(bead));

  // Its name points into the gap where the cell and two of its neighbours meet.
  const outside = ctx.part("extracellular", radial(SPOT.junction + GAP_TURN).multiplyScalar((2 * R + style.neighbourGap) / Math.sqrt(3)).setY(CUT - 0.5));
  const beyond = (count) => {
    const found = [];
    let guard = 0;
    while (found.length < count && guard++ < count * 80) {
      const point = unit(random).multiplyScalar(R + (real ? 0.25 : 1.3) + random() * 6);
      if (point.y > CUT + 0.6 || neighbours.some((at) => point.distanceTo(at) < R + (real ? 0.2 : 1))) continue;
      found.push(point);
    }
    return found;
  };
  if (real) outside.add(dots(beyond(6000), outside.points({ hue: "bioIon", size: 1.3, opacity: 0.5 })));
  else outside.add(instanced(new THREE.SphereGeometry(0.14, 8, 6), outside.material({ hue: "bioIon", opacity: 0.9 }), beyond(120).map((position) => ({ position, scale: 0.6 + random() * 0.7 }))));

  // What the picture says in words beside the cell (the lens writes them under the stop's name).
  // Two short lines, so they stay clear of the names in the columns beside the cell.
  handles.notes = [{ text: "One cell of the skin-like layer" }, { text: "Its round shape is the picture's choice", roomy: true }];

  handles.probes = {
    nucleus: NUCLEUS.clone().add(new THREE.Vector3(-0.9, style.nucleusRadius * 0.9, 0.9)),
    cutGel: new THREE.Vector3(-3.9, CUT, -7.6),
    uncutSide: new THREE.Vector3(4.0, -2.5, 8.8).normalize().multiplyScalar(R),
    sheetCell: new THREE.Vector3(73.4, 6.5, 31.8),
  };
  return handles;
}

// ------------------------------------------------------------------ molecules

export const MOLECULE_PATCH = onRim(SPOT.channels[1]);

/**
 * The membrane seen close, at the channel on the near side of the cut edge.
 * Schematic: tails for the lipid beads and ions moving through the pore.
 * Real: the same stretch at true proportions (bilayer about 4.5 nm, channel about 9 nm).
 */
export function buildMolecules(ctx, mode) {
  const angle = SPOT.channels[1];
  const outward = radial(angle), sideways = tangent(angle);
  const handles = { outward, centre: MOLECULE_PATCH.clone() };
  const membrane = ctx.part("membrane");
  const channel = ctx.part("channels");
  const tails = [];
  if (mode === "schematic") {
    for (let index = -9; index <= 9; index++) {
      if (Math.abs(index) < 2) continue;
      const base = onRim(angle + index * 0.0435, RIM, CUT + 0.06);
      for (const [from, to] of [[0.15, -0.02], [-0.33, -0.16]]) {
        const a = base.clone().addScaledVector(outward, from), b = base.clone().addScaledVector(outward, to);
        tails.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
    }
    handles.ionPath = (t) => MOLECULE_PATCH.clone().addScaledVector(outward, 1.3 - t * 2.7).setY(CUT + 0.12);
    handles.ions = Array.from({ length: 6 }, () => new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 8), channel.material({ hue: "bioIon", emissive: 0.25, roughness: 0.3 })));
    handles.view = [5.4, 3.6];
  } else {
    // True proportions: lipid head groups under a nanometre across, in two leaflets 3.8 nm apart.
    const heads = [];
    for (let index = -70; index <= 70; index++) {
      const base = MOLECULE_PATCH.clone().addScaledVector(sideways, index * 0.85 * NM).setY(CUT + 0.5 * NM);
      if (Math.abs(index * 0.85) < 5.2 || Math.abs(index * 0.85 - 24) < 6) continue; // the channel and the pump stand here
      for (const leaflet of [1.9, -1.9]) {
        const head = base.clone().addScaledVector(outward, leaflet * NM);
        const end = base.clone().addScaledVector(outward, leaflet * 0.12 * NM);
        heads.push({ position: head });
        tails.push(head.x, head.y, head.z, end.x, end.y, end.z);
      }
    }
    membrane.add(instanced(new THREE.SphereGeometry(0.4 * NM, 10, 8), membrane.material({ hue: "bioMembrane", shade: 0.22, roughness: 0.3 }), heads));
    // A channel: two walls about 3 nm thick and 10 nm long, with a pore between.
    const wall = new THREE.CapsuleGeometry(1.5 * NM, 7 * NM, 6, 12).rotateZ(Math.PI / 2);
    channel.add(
      instanced(wall, channel.material({ hue: "bioProtein", roughness: 0.35 }), [-2.2, 2.2].map((offset) => ({ position: MOLECULE_PATCH.clone().addScaledVector(sideways, offset * NM).setY(CUT + 0.5 * NM), turn: turnY(-angle) })))
    );
    // A pump beside it: larger, with most of its bulk on the cytoplasm side.
    const pump = ctx.part("pumps");
    const lobes = pump.material({ hue: "bioPump", roughness: 0.35 });
    for (const [inward, size] of [[0, 4.2], [5.5, 3.6], [-3.2, 2.6]]) {
      const lobe = new THREE.Mesh(new THREE.SphereGeometry(size * NM, 18, 14), lobes);
      lobe.position.copy(MOLECULE_PATCH).addScaledVector(sideways, 24 * NM).addScaledVector(outward, -inward * NM).setY(CUT + 0.5 * NM);
      pump.add(lobe);
    }
    handles.ionPath = (t) => MOLECULE_PATCH.clone().addScaledVector(outward, (11 - t * 22) * NM).setY(CUT + 0.9 * NM);
    handles.ions = Array.from({ length: 7 }, () => new THREE.Mesh(new THREE.SphereGeometry(0.22 * NM, 10, 8), channel.material({ hue: "bioIon", emissive: 0.25, roughness: 0.3 })));
    handles.view = [0.085, 0.056];
    handles.fromInside = true;
  }
  handles.ions.forEach((ion) => channel.add(ion));
  const strands = new THREE.BufferGeometry();
  strands.setAttribute("position", new THREE.Float32BufferAttribute(tails, 3));
  ctx.illustrate(new THREE.LineSegments(strands, ctx.neutralLine({ opacity: 0.8, colour: "ghost" })));
  return handles;
}

// ------------------------------------------------------------------ tissue

export const HEX = { radius: 10.6, height: 13, rings: 6 };
// How far the layer is drawn beyond the sheet, as outlines: out to this ring, at this strength.
const LAYER_BEYOND = [[HEX.rings + 2, 0.34], [HEX.rings + 4, 0.2], [HEX.rings + 5, 0.1]];

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
  const body = instanced(prism, sheet.material({ hue: "bioCell", roughness: 0.5 }), plain.map((cell) => ({ position: hexCentre(cell) })));
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
  const out = new THREE.Mesh(prism, replacement.material({ hue: "bioCell", opacity: 0.5, depthWrite: false }));
  out.position.copy(hexCentre(leaving)).y = HEX.height * 1.25;
  const incoming = new THREE.Mesh(prism, replacement.material({ hue: "bioCell", shade: 0.25 }));
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
  mechanics.add(instanced(prism, mechanics.material({ hue: "bioCell", opacity: 0.32, depthWrite: false }), patch.map((cell) => ({ position: hexCentre(cell) }))));
  const edgeMaterial = mechanics.material({ hue: "bioCell", shade: -0.3 });
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
  // The layer goes on beyond the sheet: more cells of the same size, drawn as outlines only
  // and fainter with distance. Scenery: it says the sheet is a patch of a larger layer. It
  // ends where the back of the worm's head begins to curve away from the flat sheet.
  const ringOf = (cell) => Math.max(Math.abs(cell.q), Math.abs(cell.r), Math.abs(cell.q + cell.r));
  const drawn = new Set();
  let inner = HEX.rings;
  for (const [outer, opacity] of LAYER_BEYOND) {
    const segments = [];
    for (const cell of sheetCells(outer)) {
      if (ringOf(cell) <= inner) continue;
      for (let index = 0; index < 6; index++) {
        const a = corner(cell, index), b = corner(cell, (index + 1) % 6);
        const key = [a, b].map((point) => `${point.x.toFixed(1)},${point.z.toFixed(1)}`).sort().join("|");
        if (drawn.has(key)) continue;
        drawn.add(key);
        segments.push(a, b);
      }
    }
    ctx.illustrate(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(segments), ctx.neutralLine({ opacity })));
    inner = outer;
  }

  // What the sheet stands for (the lens writes it under the stop's name).
  const notes = [{ text: "The sheet stands for skin-like tissue: a single layer of cells", short: "Stands for skin-like tissue" }];
  return { extent: HEX.radius * Math.sqrt(3) * (HEX.rings * 2 + 1), notes };
}

// ------------------------------------------------------------------ larger scales (placeholders)
//
// A planarian flatworm and its brain, drawn as outlines. Both are placeholders: nothing at
// these scales is simulated, and the plan has chosen neither an organ nor a species.
//
// The scales are nested, so zooming out leads from one into the next (the user, 14 November
// 2026: with the worm beside the sheet it "is just hanging there"). The sheet lies on the
// back of the worm's head, the brain lies in the head under it, and the head is the front
// of the whole worm. The sheet stands for skin-like tissue, a single layer of cells lying
// over the brain; it is placed there for the scales only, the simulated sheet is not this
// animal's tissue, and the notes say so. The brain's own cells are neurons and glia, which
// Cells does not model.
//
// Sizes are indicative. The worm is drawn 10 mm long and 1.3 mm wide, with a brain a
// little under 1 mm long. One web search (14 November 2026) gave roughly 20 mm by 2 mm
// for a planarian, from an unreviewed preprint, and no measurement of the brain.

const WORM = {
  length: 10000,
  halfWidth: 650, // at the widest part of the body
  flatness: 0.32, // thickness over width
  brainAt: 790, // from the front tip to the middle of the brain
  brainLevel: -30, // the brain's height in the body: a little below the middle
};
const ease = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const WIDE = WORM.halfWidth / 650;
/**
 * Where the worm's front tip is; everything below is built from there, along +x. It is
 * placed so that the sheet (at the origin) rests on the back of the head, on the midline
 * above the brain, where the back is nearly flat.
 */
const WORM_ORIGIN = new THREE.Vector3(-WORM.brainAt, -wormHalfWidth(WORM.brainAt / WORM.length) * WORM.flatness - 3, 0);
/** The brain: about 0.9 mm long and 0.7 mm across. `radius` is half its longer side. */
export const ORGAN = { length: 900, width: 700, radius: 450, centre: new THREE.Vector3(0, WORM_ORIGIN.y + WORM.brainLevel, 0) };
export const BODY = { length: WORM.length, width: WORM.halfWidth * 2, centre: new THREE.Vector3(WORM_ORIGIN.x + WORM.length / 2, WORM_ORIGIN.y, 0) };
const SHEET_RADIUS = (HEX.radius * Math.sqrt(3) * (HEX.rings * 2 + 1)) / 2;
const SHEET_NOTE = "The sheet, to scale: it stands for skin-like tissue over the brain";

/** Half the body's width at t (0 at the front tip, 1 at the tail tip), without the auricles. */
function wormHalfWidth(t) {
  // A rounded, triangular head, a slight neck, the widest part before the middle, a tapering tail.
  const front = t < 0.05 ? 480 * Math.pow(t / 0.05, 0.58) : 470 + 10 * (1 - ease(0.05, 0.09, t)) + 180 * ease(0.09, 0.4, t);
  const tail = t > 0.55 ? 1 - Math.pow((t - 0.55) / 0.45, 1.8) : 1;
  return front * tail * WIDE;
}

/** The auricles: a short flap on each side of the head, steep in front and swept back. */
const auricle = (t) => 80 * WIDE * Math.exp(-Math.pow((t - 0.05) / (t < 0.05 ? 0.012 : 0.024), 2));

/** A point on the worm's surface: t along the body, angle round it (0 on the right edge, a quarter turn on the back). */
function wormSurface(t, angle) {
  const half = wormHalfWidth(t);
  const side = Math.cos(angle);
  // The flaps are thin, so they add width only near the edges.
  return new THREE.Vector3(t * WORM.length, half * WORM.flatness * Math.sin(angle), (half + auricle(t) * Math.pow(Math.abs(side), 6)) * side);
}

const pairs = (points, out, closed = false) => {
  for (let index = 0; index + 1 < points.length; index++) out.push(points[index], points[index + 1]);
  if (closed) out.push(points[points.length - 1], points[0]);
};
const lineGeometry = (segments) => new THREE.BufferGeometry().setFromPoints(segments);

let planarian = null;
/**
 * The worm and its nervous system, built once in the worm's own frame and drawn at both
 * scales, so the brain seen alone and the brain in the worm's head are the same shape.
 */
function planarianShapes() {
  if (planarian) return planarian;
  const LENGTH = WORM.length;
  // Stations along the body, closer together in the head: a coarse list for the click
  // skin and a fine one for the lines, so the head's outline stays smooth.
  const stations = Array.from({ length: 73 }, (_, index) => Math.pow(index / 72, 1.45));
  const fine = Array.from({ length: 261 }, (_, index) => Math.pow(index / 260, 1.35));

  // The outline seen from above.
  const edge = [];
  for (const t of fine) edge.push(wormSurface(t, 0));
  for (const t of [...fine].reverse().slice(1, -1)) edge.push(wormSurface(t, Math.PI));
  const silhouette = lineGeometry(edge.flatMap((point, index) => [point, edge[(index + 1) % edge.length]]));
  // The same outline filled, very faintly, so the worm reads as a body and not only as lines.
  const fill = new THREE.ShapeGeometry(new THREE.Shape(edge.map((point) => new THREE.Vector2(point.x, point.z))), 1).rotateX(Math.PI / 2);

  // The body: evenly spaced rings round it and lines along it.
  const around = 20;
  const body = [];
  for (let t = 0.04; t < 0.97; t += 0.04) pairs(Array.from({ length: 28 }, (_, step) => wormSurface(t, (step / 28) * Math.PI * 2)), body, true);
  for (const turn of [0.25, 0.5, 0.75, 1.25, 1.5, 1.75]) pairs(fine.map((t) => wormSurface(t, turn * Math.PI)), body);

  // A skin of triangles over the same stations: it is never drawn, only clicked.
  const skin = new THREE.BufferGeometry();
  const corners = [], faces = [];
  for (const t of stations) for (let step = 0; step < around; step++) corners.push(wormSurface(t, (step / around) * Math.PI * 2));
  for (let row = 0; row + 1 < stations.length; row++) {
    for (let step = 0; step < around; step++) {
      const a = row * around + step, b = row * around + ((step + 1) % around);
      faces.push(a, a + around, b, b, a + around, b + around); // wound to face outwards
    }
  }
  skin.setFromPoints(corners);
  skin.setIndex(faces);

  // Two eyespots on the back of the head, and the pharynx in the middle of the body.
  const marks = [];
  const eyes = [];
  const loop = (centre, radiusX, radiusZ, count = 28) => Array.from({ length: count }, (_, step) => new THREE.Vector3(centre.x + Math.cos((step / count) * Math.PI * 2) * radiusX, centre.y, centre.z + Math.sin((step / count) * Math.PI * 2) * radiusZ));
  for (const side of [-1, 1]) {
    const at = 0.043, away = 175 * WIDE * side;
    const height = wormHalfWidth(at) * WORM.flatness * Math.sqrt(Math.max(0, 1 - Math.pow(away / wormHalfWidth(at), 2))) + 4;
    const centre = new THREE.Vector3(at * LENGTH, height, away);
    pairs(loop(centre, 72 * WIDE, 60 * WIDE), marks, true);
    eyes.push(new THREE.Vector3(centre.x + 8, centre.y + 1, centre.z - side * 22 * WIDE)); // the pigment cup sits towards the midline
  }
  const pharynx = new THREE.Vector3(0.55 * LENGTH, 0, 0);
  pairs(loop(pharynx, 820, 185 * WIDE, 44), marks, true);
  pairs(loop(new THREE.Vector3(pharynx.x + 700, 0, 0), 70, 70 * WIDE, 16), marks, true); // the mouth, at its hind end

  // The nervous system. The brain is one bent body: back along one side, round the front
  // and back along the other, so it reads as two lobes joined at the front. A nerve cord
  // leaves the hind end of each lobe and runs to the tail, with links across like rungs.
  const nerves = [];
  const level = WORM.brainLevel;
  const BEND = 165, ARM = 640, SPLAY = 0.16; // the front bend's radius, a lobe's length, how far the lobes part
  const FRONT = WORM.brainAt - 190; // where the bend's centre lies, from the front tip
  const brainLength = 2 * ARM + Math.PI * BEND;
  /** The brain's middle line at a distance along it: the point, which way it runs, the outer side, and half its width. */
  const brainAt = (distance) => {
    let point, run, half;
    if (distance < ARM || distance > ARM + Math.PI * BEND) {
      const side = distance < ARM ? -1 : 1;
      const back = side < 0 ? ARM - distance : distance - ARM - Math.PI * BEND; // from the bend towards the tail
      const q = back / ARM;
      point = new THREE.Vector3(FRONT + back * Math.cos(SPLAY), level, side * (BEND + back * Math.sin(SPLAY)));
      run = new THREE.Vector3(side * Math.cos(SPLAY), 0, Math.sin(SPLAY));
      half = (112 + 44 * Math.sin(Math.PI * Math.min(1, q / 0.6))) * (1 - 0.66 * ease(0.45, 1, q));
    } else {
      const angle = -Math.PI / 2 + (distance - ARM) / BEND;
      point = new THREE.Vector3(FRONT - BEND * Math.cos(angle), level, BEND * Math.sin(angle));
      run = new THREE.Vector3(Math.sin(angle), 0, Math.cos(angle));
      half = 112 - 20 * Math.cos(angle);
    }
    return { point, run, out: run.clone().cross(UP), half: half * WIDE };
  };
  const spine = Array.from({ length: 121 }, (_, index) => brainAt((index / 120) * brainLength));
  const round = (station, count) => Array.from({ length: count }, (_, step) => {
    const angle = (step / count) * Math.PI * 2;
    return station.point.clone().addScaledVector(station.out, Math.cos(angle) * station.half).addScaledVector(UP, Math.sin(angle) * station.half * 0.6);
  });
  // Its outline seen from above, the ridge along its top and bottom, and rings round it.
  const outer = spine.map((station) => station.point.clone().addScaledVector(station.out, station.half));
  const inner = spine.map((station) => station.point.clone().addScaledVector(station.out, -station.half));
  pairs([...outer, ...inner.reverse()], nerves, true);
  for (const lift of [0.6, -0.6]) pairs(spine.map((station) => station.point.clone().addScaledVector(UP, station.half * lift)), nerves);
  spine.forEach((station, index) => {
    if (index % 8 === 4) pairs(round(station, 18), nerves, true);
  });
  // The same body as a skin of triangles: never drawn, only clicked.
  const brainSkin = new THREE.BufferGeometry();
  const sides = 10, hull = [], hullFaces = [];
  for (const station of spine) hull.push(...round(station, sides));
  for (let row = 0; row + 1 < spine.length; row++) {
    for (let step = 0; step < sides; step++) {
      const a = row * sides + step, b = row * sides + ((step + 1) % sides);
      hullFaces.push(a, a + sides, b, b, a + sides, b + sides);
    }
  }
  brainSkin.setFromPoints(hull);
  brainSkin.setIndex(hullFaces);
  // Short nerves from the outer side of the brain towards the edge of the head.
  const forward = new THREE.Vector3(-1, 0, 0);
  for (const [fraction, reach] of [[0.1, 150], [0.2, 190], [0.3, 215], [0.385, 215], [0.44, 180]]) {
    for (const from of [fraction, 1 - fraction]) {
      const station = brainAt(from * brainLength);
      const root = station.point.clone().addScaledVector(station.out, station.half);
      const tip = root.clone().add(station.out.clone().addScaledVector(forward, 0.45).normalize().multiplyScalar(reach * WIDE));
      const room = wormHalfWidth(Math.max(0.004, tip.x / LENGTH)) - 35; // keep the tip inside the head
      if (Math.abs(tip.z) > room) tip.z = Math.sign(tip.z) * room;
      nerves.push(root, tip);
    }
  }
  // The cords settle halfway between the midline and the edge, and meet in the tail.
  const hind = brainAt(brainLength).point;
  const cordAside = (t) => hind.z + (wormHalfWidth(t) * 0.5 - hind.z) * ease(hind.x / LENGTH, hind.x / LENGTH + 0.075, t);
  for (const side of [-1, 1]) {
    const cord = [new THREE.Vector3(hind.x, level, side * hind.z)];
    for (let t = hind.x / LENGTH + 0.008; t < 0.972; t += 0.0125) cord.push(new THREE.Vector3(t * LENGTH, level, side * cordAside(t)));
    cord.push(new THREE.Vector3(0.975 * LENGTH, level, 0));
    pairs(cord, nerves);
  }
  for (let t = 0.175; t < 0.94; t += 0.045) nerves.push(new THREE.Vector3(t * LENGTH, level, -cordAside(t)), new THREE.Vector3(t * LENGTH, level, cordAside(t)));

  planarian = { silhouette, fill, body: lineGeometry(body), skin, marks: lineGeometry(marks), eyes, nerves: lineGeometry(nerves), brainSkin };
  return planarian;
}

/** Puts something built in the worm's frame where the worm lies. */
function inWorm(object) {
  object.position.copy(WORM_ORIGIN);
  return object;
}

/** A ring the size of the sheet, where the sheet is: on the back of the worm's head. */
function sheetRing(ctx, zoneName, band, noteAt, text, roomy = false) {
  const ring = new THREE.Mesh(new THREE.RingGeometry(SHEET_RADIUS * (1 - band), SHEET_RADIUS * (1 + band), 48), ctx.neutral({ opacity: 0.9, colour: "fg", side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 1;
  ctx.illustrate(ring, zoneName);
  // "roomy" marks a note that is written only where the screen is wide enough for it.
  return { text, anchor: new THREE.Vector3(roomy ? SHEET_RADIUS * 3 : 0, 0, noteAt), roomy };
}

/**
 * The organ: planned, so a sketch. Drawn as a planarian's brain with its nerve cords.
 * Returns the notes the lens writes beside it.
 */
export function buildOrgan(ctx) {
  const shapes = planarianShapes();
  const organ = ctx.scale("scale.organ", ORGAN.centre.clone().add(new THREE.Vector3(-520, 110, -WORM.halfWidth - 40)));
  organ.add(inWorm(new THREE.LineSegments(shapes.nerves, organ.lineMaterial({ opacity: 0.95 }))));
  organ.add(inWorm(new THREE.Mesh(shapes.brainSkin, organ.proxyMaterial())));
  // The outline of the worm's head, faint, so the brain is seen where it lies.
  ctx.illustrate(inWorm(new THREE.LineSegments(shapes.silhouette, ctx.neutralLine({ opacity: 0.4 }))), "organ");
  ctx.illustrate(inWorm(new THREE.Mesh(shapes.fill, ctx.neutral({ opacity: 0.06, side: THREE.DoubleSide }))), "organ");
  const notes = [sheetRing(ctx, "organ", 0.018, SHEET_RADIUS * 1.5, SHEET_NOTE)];
  const beside = ORGAN.centre.clone().add(new THREE.Vector3(330, 0, WORM.halfWidth + 120));
  notes.push({ text: "A planarian's brain and nerve cords: a placeholder outline", anchor: beside });
  notes.push({ text: "The brain's own cells, neurons and glia, are not modelled", anchor: beside, lift: -22, roomy: true });
  return { notes };
}

/**
 * The whole organism: a long-term goal, so a sketch. Drawn as a planarian flatworm, with
 * the same brain in its head. Returns the notes the lens writes beside it.
 */
export function buildOrganism(ctx) {
  const shapes = planarianShapes();
  const organism = ctx.scale("scale.organism", BODY.centre.clone().add(new THREE.Vector3(0, 240, -WORM.halfWidth - 260)));
  organism.add(inWorm(new THREE.LineSegments(shapes.body, organism.lineMaterial({ opacity: 0.5 }))));
  organism.add(inWorm(new THREE.LineSegments(shapes.silhouette, organism.lineMaterial({ opacity: 1 }))));
  organism.add(inWorm(new THREE.LineSegments(shapes.marks, organism.lineMaterial({ opacity: 0.9 }))));
  organism.add(inWorm(new THREE.LineSegments(shapes.nerves, organism.lineMaterial({ opacity: 0.8 }))));
  organism.add(inWorm(new THREE.Mesh(shapes.skin, organism.proxyMaterial())));
  ctx.illustrate(inWorm(new THREE.Mesh(shapes.fill, ctx.neutral({ opacity: 0.07, side: THREE.DoubleSide }))), "organism");
  const cup = new THREE.CircleGeometry(30 * WIDE, 16).rotateX(-Math.PI / 2);
  ctx.illustrate(instanced(cup, ctx.neutral({ opacity: 0.85, colour: "fg", side: THREE.DoubleSide }), shapes.eyes.map((eye) => ({ position: eye.clone().add(WORM_ORIGIN) }))), "organism");
  const notes = [sheetRing(ctx, "organism", 0.09, -SHEET_RADIUS - 520, "The sheet, to scale", true)];
  notes.push({ text: "A planarian flatworm: a placeholder outline", anchor: BODY.centre.clone().add(new THREE.Vector3(BODY.length * 0.1, 0, WORM.halfWidth + 620)) });
  return { notes };
}

export { glyphSprite };
