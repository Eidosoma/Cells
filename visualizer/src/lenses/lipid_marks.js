// Lipids as things: the meshes of the assembly view's molecules (src/lenses/lineage.js). An
// amphiphile has a head that likes water and two tails that do not. The head's form and colour say
// its type: the three leading types each have a hue and a form of their own (a soft diamond, a soft
// cube, a soft tetrahedron), so they stay apart for a reader who does not see colour as most do;
// every other type is a round head in one of two greys. The tails are the same for every type and
// flex with the water's clock. How a lipid looks, every size and every motion is the picture's own:
// no law of Cells computes how the lipids move and pack.
//
// Cost: one set of instances for every lipid drawn (in the assembly, in flight, in the water), so a
// frame draws four heads' meshes, one of tails and one of glows, whatever their number; nothing is
// made per frame.

import * as THREE from "../three.js";
import { mergeGeometries, mergeVertices } from "three/addons/utils/BufferGeometryUtils.js";
import { wetten } from "./lipid_water.js";

/** The size of a head, in the scene's units (an assembly of 80 molecules is about one across its radius). */
export const HEAD = 0.155;
/** How long a tail is, against its assembly's radius, and at most. */
export const TAIL = { share: 0.78, longest: 0.82 };
/** The forms of the heads, by slot: the three leading types, then the rest. */
export const FORMS = ["soft diamond", "soft cube", "soft tetrahedron", "round"];
const GLOW_CAP = 10;

/** Smooth normals: three.js's polyhedra come with a vertex for each face's corner, so they are joined first. */
function smoothed(geometry) {
  geometry.deleteAttribute("normal");
  geometry.deleteAttribute("uv");
  const joined = mergeVertices(geometry, 1e-5);
  geometry.dispose();
  joined.computeVertexNormals();
  return joined;
}

/** A superellipsoid's surface along each direction of a sphere: |x|^p + |y|^p + |z|^p = 1. */
function rounded(power, detail = 3, squash = 1) {
  const geometry = new THREE.IcosahedronGeometry(1, detail);
  const position = geometry.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < position.count; i++) {
    v.fromBufferAttribute(position, i).normalize();
    const n = Math.pow(Math.pow(Math.abs(v.x), power) + Math.pow(Math.abs(v.y), power) + Math.pow(Math.abs(v.z), power), 1 / power);
    v.divideScalar(n);
    v.y *= squash;
    position.setXYZ(i, v.x, v.y, v.z);
  }
  return smoothed(geometry);
}

/** A tetrahedron with its corners and edges worn round. */
function softTetrahedron(detail = 3) {
  const geometry = new THREE.TetrahedronGeometry(1, detail);
  const position = geometry.attributes.position;
  const v = new THREE.Vector3(), s = new THREE.Vector3();
  for (let i = 0; i < position.count; i++) {
    v.fromBufferAttribute(position, i);
    s.copy(v).normalize();
    v.lerp(s, 0.42).multiplyScalar(1.12);
    position.setXYZ(i, v.x, v.y, v.z);
  }
  // A point up the lipid's axis, so the form reads the same way on every lipid.
  geometry.rotateX(Math.atan(Math.SQRT2) - Math.PI / 2).rotateZ(Math.PI / 4);
  return smoothed(geometry);
}

/** The heads' forms, at the head's size: the head sits on the lipid's axis, its centre at y = 0. */
export function headForms({ narrow = false } = {}) {
  const detail = narrow ? 2 : 3;
  const forms = [rounded(1.35, detail), rounded(4.5, detail), softTetrahedron(narrow ? 3 : 5), new THREE.SphereGeometry(1, narrow ? 12 : 16, narrow ? 8 : 12)];
  const sizes = [1.18, 0.86, 1.05, 1];
  forms.forEach((geometry, slot) => geometry.scale(HEAD * sizes[slot], HEAD * sizes[slot], HEAD * sizes[slot]));
  return forms;
}

/**
 * Two tails and the short neck that joins them to the head, along -y from the head's foot (y = 0)
 * to the tips (y = -1): the instance's matrix stretches it to its length. Each tail is a thin tube
 * that thins to its tip, with a soft kink a third of the way down, as a lipid's unsaturated tail has.
 */
export function tailForm({ narrow = false } = {}) {
  const radial = narrow ? 5 : 6, rows = narrow ? 5 : 8;
  const parts = [];
  for (const side of [-1, 1]) {
    const tube = new THREE.CylinderGeometry(0.024, 0.015, 1, radial, rows, false).translate(0, -0.5, 0);
    const position = tube.attributes.position;
    for (let i = 0; i < position.count; i++) {
      const y = position.getY(i), u = -y;
      // apart at the neck, closer toward the tips; one tail bends a little a third of the way down
      const apart = 0.05 * (1 - 0.55 * u) * side;
      const kink = side > 0 ? 0.035 * Math.min(1, Math.max(0, (u - 0.33) / 0.2)) : 0;
      position.setX(i, position.getX(i) + apart + kink);
    }
    tube.computeVertexNormals();
    parts.push(tube);
  }
  const neck = new THREE.CylinderGeometry(0.05, 0.04, 0.12, radial, 1, false).translate(0, -0.02, 0);
  parts.push(neck);
  const merged = mergeGeometries(parts.map((part) => part.toNonIndexed()));
  for (const part of parts) part.dispose();
  return merged;
}

/** The materials of the lipids: wet heads, waxy tails, and the soft glow of a molecule that has just come. */
export function lipidMaterials(water) {
  const heads = new THREE.MeshPhysicalMaterial({ roughness: 0.3, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.16, sheen: 0.35, sheenRoughness: 0.45, sheenColor: new THREE.Color(1, 1, 1), envMapIntensity: 0.7, toneMapped: false });
  wetten(heads, water, { caustics: 1, rim: 0.4, rimPower: 2.4, deep: 0.25 });
  const tails = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0, envMapIntensity: 0.45 });
  wetten(tails, water, { caustics: 0.45, rim: 0.22, rimPower: 2, flex: true, deep: 0.82 });
  // A soft halo: brightest where the ball faces the camera, nothing at its rim, so it reads as light round the molecule.
  const glow = new THREE.ShaderMaterial({
    uniforms: { color: { value: new THREE.Color(1, 1, 1) }, opacity: { value: 0.32 } },
    vertexShader: `varying vec3 vNormal; varying vec3 vView;
      void main() { vec4 p = modelViewMatrix * instanceMatrix * vec4(position, 1.0); vNormal = normalize(normalMatrix * mat3(instanceMatrix) * normal); vView = normalize(-p.xyz); gl_Position = projectionMatrix * p; }`,
    fragmentShader: `uniform vec3 color; uniform float opacity; varying vec3 vNormal; varying vec3 vView;
      void main() { float f = pow(clamp(dot(normalize(vNormal), normalize(vView)), 0.0, 1.0), 2.2); gl_FragColor = vec4(color, f * opacity);
      #include <colorspace_fragment>
      }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false, fog: false,
  });
  glow.color = glow.uniforms.color.value;
  glow.userData.noContact = true;
  return { heads, tails, glow };
}

/**
 * The instances of every lipid drawn. A lipid to draw is { pos [x, y, z], axis [x, y, z] (from its
 * tails to its head, unit), spin (radians about the axis), slot (0 to 3), colour (THREE.Color),
 * scale, tail (its length), flex (how much its tails bend, 0 to 1), phase, glow (0 to 1), id }.
 */
export class LipidMeshes {
  constructor(parent, materials, { capacity = 420, narrow = false } = {}) {
    this.capacity = capacity;
    this.group = new THREE.Group();
    parent.add(this.group);
    this.forms = headForms({ narrow });
    this.heads = this.forms.map((geometry, slot) => {
      const mesh = new THREE.InstancedMesh(geometry, materials.heads, capacity);
      mesh.count = 0;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3);
      mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
      mesh.frustumCulled = false;
      mesh.userData.slot = slot;
      this.group.add(mesh);
      return mesh;
    });
    const tail = tailForm({ narrow });
    this.flex = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 2), 2);
    this.flex.setUsage(THREE.DynamicDrawUsage);
    tail.setAttribute("aFlex", this.flex);
    this.tails = new THREE.InstancedMesh(tail, materials.tails, capacity);
    this.tails.count = 0;
    this.tails.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.tails.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3);
    this.tails.instanceColor.setUsage(THREE.DynamicDrawUsage);
    this.tails.frustumCulled = false;
    this.tails.userData.unpickable = true;
    this.group.add(this.tails);
    this.glows = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 14, 10), materials.glow, GLOW_CAP);
    this.glows.count = 0;
    this.glows.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.glows.frustumCulled = false;
    this.glows.userData.unpickable = true;
    this.group.add(this.glows);
    this.lists = [[], [], [], []];
    this.matrix = new THREE.Matrix4();
    this.quaternion = new THREE.Quaternion();
    this.spin = new THREE.Quaternion();
    this.up = new THREE.Vector3(0, 1, 0);
    this.axis = new THREE.Vector3();
    this.at = new THREE.Vector3();
    this.size = new THREE.Vector3();
    this.foot = new THREE.Vector3();
    this.lit = new THREE.Color();
    this.white = new THREE.Color(1, 1, 1);
  }

  /** Draw these lipids; `chosen(lipid)` says whether one is of the type chosen. */
  draw(lipids, { tailColour, chosenColour = null, chosen = null } = {}) {
    const { matrix, quaternion, spin, up, axis, at, size, foot } = this;
    const counts = [0, 0, 0, 0];
    this.lists = [[], [], [], []];
    let tails = 0, glows = 0;
    const flex = this.flex.array;
    for (const lipid of lipids) {
      const slot = lipid.slot;
      const index = counts[slot];
      if (index >= this.capacity || tails >= this.capacity) continue;
      counts[slot]++;
      this.lists[slot][index] = lipid;
      axis.set(lipid.axis[0], lipid.axis[1], lipid.axis[2]);
      quaternion.setFromUnitVectors(up, axis.lengthSq() > 1e-9 ? axis.normalize() : up);
      spin.setFromAxisAngle(up, lipid.spin || 0);
      quaternion.multiply(spin);
      const scale = Math.max(1e-3, lipid.scale ?? 1);
      at.set(lipid.pos[0], lipid.pos[1], lipid.pos[2]);
      const pick = chosen && chosen(lipid);
      size.setScalar(scale * (pick ? 1.3 : 1));
      matrix.compose(at, quaternion, size);
      const head = this.heads[slot];
      head.setMatrixAt(index, matrix);
      // A type chosen keeps its own colour, so that it is not taken for another type's: larger, and lighter.
      head.setColorAt(index, pick ? (chosenColour || this.lit.copy(lipid.colour).lerp(this.white, 0.28)) : lipid.colour);
      // The tails hang from the head's foot, along the axis inward.
      foot.copy(axis).multiplyScalar(-HEAD * 0.72 * scale).add(at);
      size.set(scale, Math.max(0.05, (lipid.tail ?? 0.6) * scale), scale);
      matrix.compose(foot, quaternion, size);
      this.tails.setMatrixAt(tails, matrix);
      this.tails.setColorAt(tails, lipid.tint || tailColour);
      flex[tails * 2] = lipid.phase || 0;
      flex[tails * 2 + 1] = lipid.flex ?? 1;
      tails++;
      if (lipid.glow > 0 && glows < GLOW_CAP) {
        size.setScalar(HEAD * (1.4 + 2.2 * (1 - lipid.glow)) * scale);
        matrix.compose(at, quaternion, size);
        this.glows.setMatrixAt(glows++, matrix);
      }
    }
    this.heads.forEach((mesh, slot) => {
      mesh.count = counts[slot];
      mesh.instanceMatrix.needsUpdate = true;
      mesh.instanceColor.needsUpdate = true;
      // A ray is first held against the bounds, which three.js works out again when next asked.
      mesh.boundingSphere = null;
    });
    this.tails.count = tails;
    this.tails.instanceMatrix.needsUpdate = true;
    this.tails.instanceColor.needsUpdate = true;
    this.flex.needsUpdate = true;
    this.glows.count = glows;
    this.glows.instanceMatrix.needsUpdate = true;
  }

  /** The lipid a picking ray hit. */
  lipidOf(hit) {
    const slot = hit.object.userData.slot;
    return slot === undefined ? null : this.lists[slot][hit.instanceId] || null;
  }

  dispose() {
    for (const mesh of [...this.heads, this.tails, this.glows]) mesh.geometry.dispose();
  }
}
