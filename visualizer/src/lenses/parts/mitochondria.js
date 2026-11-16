// The mitochondria and the fuel they make, or the fuel alone in a cell without them.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT, MITO_AT_SURFACE } from "../cell_layout.js";
import { unit, UP, along, radial, instanced, dots } from "./geometry.js";

export default {
  kind: "mitochondria",
  draws: ["mitochondria", "atp"],
  build(env) {
    const { ctx } = env;
    const { real, style, has, organelle, outline, random, inside, vacuole, inCytoplasm, scatter, seat, NUCLEUS, coreAt, coreRadius } = env.layout;
    if (!organelle("mitochondria")) {
      // No mitochondria: the fuel is made in the cytoplasm, and is drawn through it near the cut.
      if (has("atp")) {
        const fuel = ctx.part("atp", seat(new THREE.Vector3(-0.9, CUT + 0.55, 7.4), 1.3));
        const sparks = scatter(real ? 400 : 30, (point) => inside(point) > 0.9 && point.y < CUT + 0.2 && point.y > CUT - 1.4 && point.distanceTo(coreAt) > coreRadius * 0.5);
        fuel.add(instanced(new THREE.SphereGeometry(0.17, 12, 9), fuel.material({ hue: "bioFuel", emissive: 0.22, roughness: 0.3 }), sparks.map((position) => ({ position, scale: 0.8 + random() * 0.5 }))));
      }
    } else {
    const lying = MITO_AT_SURFACE.map(([x, z, turn, margin]) => ({ at: seat(new THREE.Vector3(x, CUT - 0.12, z), margin), turn }));
    const mitochondria = ctx.part("mitochondria", lying[1].at.clone().setY(CUT + 0.75));
    const fuel = ctx.part("atp", new THREE.Vector3(-0.9, CUT + 0.55, 7.4));
    if (!real) {
      // The shell of one cut open stays out of contact shade: the gap between its wall and the
      // floor laid in it would go dark like a pit, where the approved picture has a bright rim.
      // The folds drawn on the ones left whole are shown here as the shelves themselves.
      const outer = mitochondria.material({ hue: "bioMito", clip: true, side: THREE.DoubleSide, roughness: 0.35, thin: 0.7, contact: false });
      const matrix = mitochondria.material({ hue: "bioMito", shade: 0.5, roughness: 0.5 });
      const crista = mitochondria.material({ hue: "bioMito", shade: -0.05, roughness: 0.45 });
      const stadium = new THREE.Shape();
      stadium.absarc(1.0, 0, 0.8, -Math.PI / 2, Math.PI / 2, false);
      stadium.absarc(-1.0, 0, 0.8, Math.PI / 2, (3 * Math.PI) / 2, false);
      for (const { at, turn } of lying) {
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
        one.position.copy(at);
        one.rotation.y = turn;
        mitochondria.add(one);
      }
      const whole = mitochondria.material({ hue: "bioMito", roughness: 0.4, thin: 0.7, texture: "folds", axis: UP });
      const deep = [[-6.0, -3.0, 0.6], [0.6, -4.5, -3.4], [5.0, -3.75, 3.0], [-2.6, -4.9, 4.0], [-3.4, -2.1, -6.4], [6.4, -2.0, -4.6]];
      // Lying roughly level, like the ones at the surface.
      const level = () => radial(random() * Math.PI * 2).setY((random() - 0.5) * 0.5);
      mitochondria.add(instanced(new THREE.CapsuleGeometry(0.8, 1.8, 8, 20), whole, deep.map((xyz) => ({ position: seat(new THREE.Vector3(...xyz), 2.5), direction: level() }))));
      const sparks = [];
      for (const [x, z] of [...lying.map(({ at }) => [at.x, at.z]), [-0.9, 7.2]]) {
        for (let index = 0; index < 7; index++) {
          const angle = random() * Math.PI * 2, reach = 1.5 + random() * 0.9;
          const point = new THREE.Vector3(x + Math.cos(angle) * reach * 1.25, CUT + 0.12 + random() * 0.3, z + Math.sin(angle) * reach);
          if (outline.depth(point.x, point.z) > 1.1 && point.distanceTo(NUCLEUS) > style.nucleusRadius + 0.6) sparks.push({ position: point, scale: 0.8 + random() * 0.5 });
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
      // The shelves are thin and soft: a little light comes through them. The clear outer membrane stays glass.
      // They stand so close that contact shade between them turned each stack brown: they stay out of it.
      const fold = mitochondria.material({ hue: "bioMito", shade: -0.06, clip: true, roughness: 0.5, thin: 0.5, contact: false });
      const placed = shapes.map(() => []);
      for (const position of many) {
        const which = Math.floor(random() * shapes.length), scale = 0.85 + random() * 0.35;
        // Turned any way that keeps both its ends inside the cell and out of the nucleus.
        const reach = (shapes[which].length / 2) * scale;
        // Beside a vacuole it lies along the side it is pressed against: across the way out of the cell there.
        const lying = () => {
          const out = new THREE.Vector3(inside(position.clone().setX(position.x - 0.05)) - inside(position.clone().setX(position.x + 0.05)), inside(position.clone().setY(position.y - 0.05)) - inside(position.clone().setY(position.y + 0.05)), inside(position.clone().setZ(position.z - 0.05)) - inside(position.clone().setZ(position.z + 0.05)));
          const way = unit(random);
          return out.lengthSq() > 1e-9 ? way.addScaledVector(out.normalize(), -way.dot(out)).normalize() : way;
        };
        let direction = vacuole ? lying() : unit(random);
        for (let tries = 0; tries < 16; tries++) {
          if ([1, -1].every((end) => inCytoplasm(position.clone().addScaledVector(direction, end * reach), 0.35, 0.45))) break;
          direction = vacuole ? lying() : unit(random);
        }
        placed[which].push({ position, turn: along(direction), scale });
      }
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
    }
  },
};
