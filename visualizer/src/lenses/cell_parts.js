// Geometry for the cell lens. Every shape built here is either bound to a capability
// from the scene file (through ctx.part) or is neutral illustration (ctx.neutral).
// Nothing is drawn that looks like a capability without being one.
//
// Units: 1 is one micrometre. The cell is a generic animal cell about 20 µm across.
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

  // ---------------------------------------------------------------- gap junctions and the neighbour
  const toward = radial(SPOT.junction);
  const neighbourAt = toward.clone().multiplyScalar(2 * R + style.neighbourGap);
  const glass = ctx.neutral({ opacity: 0.035, glass: 0.2, clip: true, side: THREE.DoubleSide });
  const neighbour = new THREE.Mesh(new THREE.SphereGeometry(R, 64, 40), glass);
  neighbour.position.copy(neighbourAt);
  neighbour.renderOrder = 7;
  ctx.illustrate(neighbour);
  if (real) {
    const line = new THREE.LineLoop(edgeLine(), ctx.neutralLine({ opacity: 0.6 }));
    line.position.copy(neighbourAt);
    ctx.illustrate(line);
  } else {
    const neighbourBand = new THREE.Mesh(new THREE.RingGeometry(RIM - style.band * 0.72, RIM + style.band * 0.28, 120), ctx.neutral({ opacity: 0.3, side: THREE.DoubleSide }));
    neighbourBand.rotation.x = -Math.PI / 2;
    neighbourBand.position.copy(neighbourAt).setY(CUT + 0.004);
    ctx.illustrate(neighbourBand);
  }
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
    // Ribosomes on the sheets (rough ER).
    const perLayer = real ? Math.round(span * radius * 22) : Math.round(span * radius * 1.7);
    for (let index = 0; index < perLayer; index++) {
      const angle = start + (span * (index + random() * 0.6)) / perLayer;
      const out = (random() < 0.5 ? 1 : -1) * (style.er.thickness / 2 + (real ? 0.012 : 0.07));
      studs.push(NUCLEUS.clone().addScaledVector(radial(angle), radius + out).setY(CUT - style.er.height * 0.12 + (random() - 0.5) * style.er.height * 0.9));
    }
  }
  if (real) {
    er.add(dots(studs, er.points({ hue: "bioRibosome", size: 1.3, opacity: 0.85 })));
    // The network reaches through the cell as tubules, and free ribosomes fill the cytosol.
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
    er.add(dots(scatter(6000), er.points({ hue: "bioRibosome", size: 1.1, opacity: 0.4 })));
  } else {
    er.add(instanced(new THREE.SphereGeometry(0.085, 8, 6), er.material({ hue: "bioRibosome", roughness: 0.4 }), studs.map((position) => ({ position }))));
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
    const capsule = mitochondria.material({ hue: "bioMito", clip: true, side: THREE.DoubleSide, roughness: 0.4 });
    mitochondria.add(instanced(new THREE.CapsuleGeometry(0.3, 1.5, 6, 12), capsule, many.map((position) => ({ position, direction: unit(random), scale: 0.8 + random() * 0.5 }))));
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

  const outside = ctx.part("extracellular", new THREE.Vector3(-12.2, CUT - 0.5, -4.5));
  const beyond = (count) => {
    const found = [];
    let guard = 0;
    while (found.length < count && guard++ < count * 40) {
      const point = unit(random).multiplyScalar(R + (real ? 0.25 : 1.3) + random() * 6);
      if (point.y > CUT + 0.6 || point.distanceTo(neighbourAt) < R + (real ? 0.2 : 1)) continue;
      found.push(point);
    }
    return found;
  };
  if (real) outside.add(dots(beyond(6000), outside.points({ hue: "bioIon", size: 1.3, opacity: 0.5 })));
  else outside.add(instanced(new THREE.SphereGeometry(0.14, 8, 6), outside.material({ hue: "bioIon", opacity: 0.9 }), beyond(120).map((position) => ({ position, scale: 0.6 + random() * 0.7 }))));

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
