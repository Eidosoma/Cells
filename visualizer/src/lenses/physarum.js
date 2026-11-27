import * as THREE from "../three.js";
import { h, emit } from "../ui/dom.js";
import { registerEntryView } from "../ui/entry_views.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { fitView } from "./laws_marks.js";

const point = (x, y, z) => new THREE.Vector3(x, y, z);
const part = id => "physarum:" + id;
const detail = {
  veins: ["Main veins", "Thick tubes link growing regions of the plasmodium. Their contractile walls drive back-and-forth flow."],
  web: ["Fine network", "Small connected tubes branch from larger veins and link adjacent routes."],
  front: ["Advancing fan", "The thin, spreading edge is part of the same multinucleate cell."],
  wall: ["Contractile wall", "The outer gel contains the actomyosin system. Contraction changes the tube cross-section and drives fluid motion."],
  fluid: ["Streaming cytoplasm", "The inner fluid moves back and forth. The direction arrows illustrate one phase at a time."],
  parcel: ["Material parcel", "Follow this same marker through a reversal. Its location is the moving quantity in this Lagrangian illustration."],
};

function surface(position, rows, columns) {
  const vertices = [], indices = [];
  for (let row = 0; row <= rows; row++) {
    for (let col = 0; col <= columns; col++) {
      const v = position(row / rows, col / columns);
      vertices.push(v.x, v.y, v.z);
      if (row === rows || col === columns) continue;
      const a = row * (columns + 1) + col, b = a + columns + 1;
      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setIndex(indices);
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geometry.computeVertexNormals();
  return geometry;
}

function tube(a, b, thick, thin, bend) {
  const direction = b.clone().sub(a);
  const side = point(-direction.z, 0, direction.x).normalize();
  return surface((t, u) => {
    const r = THREE.MathUtils.lerp(thick, thin, t), angle = u * Math.PI * 2;
    const center = a.clone().lerp(b, t).addScaledVector(side, bend * Math.sin(t * Math.PI));
    return center.addScaledVector(side, Math.cos(angle) * r).add(point(0, Math.sin(angle) * r * 0.62, 0));
  }, 10, 10);
}

const spine = [[-5.1,.12,.18],[-4,.16,.33],[-2.8,.21,.02],[-1.4,.24,-.27],
  [0,.24,-.04],[1.3,.22,.34],[2.6,.19,.27],[3.7,.13,-.15],[4.9,.1,-.48]].map(p => point(...p));
const width = [.16,.35,.7,.91,.95,.88,.69,.49,.11];

function drawNetwork(add) {
  for (let i = 1; i < spine.length; i++) {
    add("veins", tube(spine[i-1], spine[i], .21 - .012*i, .198 - .012*i, .14 * Math.sin(i*3)));
  }
  for (const side of [-1, 1]) {
    const rows = [spine];
    for (let band = 1; band <= 4; band++) {
      const nodes = spine.map((root, i) => {
        const wiggle = Math.sin(i*2.4 + band*1.55 + side) * .24;
        const spread = (.64 + wiggle) * band * width[i];
        return point(root.x + .16*band*Math.sin(i*1.43+side) + .23*band, .12-band*.018, root.z + side*spread);
      });
      rows.push(nodes);
      for (let i = 0; i < nodes.length; i++) {
        const radius = (.17 - .029*band) * (.52 + .48*width[i]);
        add(band === 1 && i % 2 ? "veins" : "web", tube(rows[band-1][i], nodes[i], radius, radius*.69, side*.047));
        if (i && (band < 4 || (i + side) % 3 !== 0))
          add("web", tube(nodes[i-1], nodes[i], radius*.67, radius*.58, .12*Math.sin(i+band*side)));
        if (i && band > 1 && (i+band)%3 === 0)
          add("web", tube(rows[band-1][i-1], nodes[i], radius*.52, radius*.41, -.075*side));
        if (i > 1 && i < nodes.length-1 && band <= 3) {
          const inner = rows[band-1][i].clone().lerp(rows[band-1][i-1],.29 + .13*Math.cos(i+band)),
            outer = nodes[i].clone().lerp(nodes[i-1],.64 + .12*Math.sin(i-band)),
            junction = inner.clone().lerp(outer,.56).add(point(.075,.016,0));
          add("web",tube(inner,junction,radius*.24,radius*.22,.08*Math.sin(i*band)));
          add("web",tube(junction,outer,radius*.23,radius*.16,-.047));
          add("web",tube(junction,nodes[i],radius*.17,radius*.12,.06));
        }
      }
    }
    for (let i = 1; i < spine.length-1; i++) {
      const root = rows[4][i], spread = width[i] * .98;
      const center = root.clone().add(point(.28, -.008, side*spread*.43));
      const front = surface((r,t) => {
        const a = t * Math.PI * 2, scallop = 1 + .16*Math.sin(a*7 + i) + .08*Math.cos(a*11);
        return center.clone().add(point(Math.cos(a)*r*(.57+.14*Math.sin(i))*scallop, .037*(1-r), Math.sin(a)*r*spread*scallop));
      }, 12, 72);
      const colors = [];
      const tint = new THREE.Color();
      const position = front.getAttribute("position");
      for (let vertex = 0; vertex < position.count; vertex++) {
        const r = Math.floor(vertex/73)/12;
        const variation = .035*Math.sin(position.getX(vertex)*44+position.getZ(vertex)*60);
        tint.setHSL(.55+.025*r,.12,.39+.37*r+variation);
        colors.push(tint.r,tint.g,tint.b);
      }
      front.setAttribute("color",new THREE.Float32BufferAttribute(colors,3));
      add("front",front);
      for (let j = 0; j < 5; j++) {
        const dest = center.clone().add(point((j-2)*.24,.026,side*spread*(.47 + .13*Math.cos(j-2))));
        add("web", tube(root.clone().lerp(center,.2), dest, .026, .007, .024*(j-2)));
      }
    }
  }
  const plate = new THREE.Mesh(new THREE.CylinderGeometry(1,1,.105,86), new THREE.MeshStandardMaterial({color:"#ab9d74",roughness:.98}));
  plate.scale.set(6.65,1,4.07);
  plate.position.set(.22,-.11,0);
  plate.userData.unpickable = true;
  return plate;
}

function drawCutaway(add) {
  const cross = (t, angle, radius) => {
    const r = radius * (1 + .11*Math.cos(t*Math.PI*3));
    return point(t*7-3.5, Math.sin(angle)*r + .13*Math.sin(t*Math.PI*2), Math.cos(angle)*r);
  };
  const start = Math.PI*.64, end = Math.PI*2.04;
  for (const r of [1.06,.9]) add("wall",surface((t,u) => cross(t, THREE.MathUtils.lerp(start,end,u),r),32,30));
  for (const a of [start,end]) add("wall",surface((t,u) => cross(t,a,THREE.MathUtils.lerp(.9,1.06,u)),32,2));
  for (const t of [0,1]) add("wall",surface((u,v) => cross(t,THREE.MathUtils.lerp(start,end,u),THREE.MathUtils.lerp(.9,1.06,v)),30,3));
  add("fluid",surface((u,t) => point(t*6.93-3.465, -.35+.13*Math.sin(t*Math.PI*2) + .018*Math.cos(u*14+t*9), (u-.5)*1.53), 21, 37));
  for (let i = 0; i < 19; i++) {
    const t = (i+.5)/19, angle = start+.33+(i%4)*.52;
    const from = cross(t,angle,1.084), to = cross(t+.019,angle+.58,1.084);
    add("wall",tube(from,to,.014,.017,.008));
  }
}

export class PhysarumLens {
  constructor(stage, labels, entry) {
    this.id = "physarum";
    this.stage = stage;
    this.labels = labels;
    this.entry = entry;
    this.level = "network";
    this.wantsLeftRoom = true;
    this.flow = "rest";
    this.phase = 0;
    this.root = new THREE.Group();
    this.network = new THREE.Group();
    this.cutaway = new THREE.Group();
    this.root.add(this.network,this.cutaway);
    const materials = {
      veins: ["#ffb72b",.42], web:["#ef9b21",.48], front:["#eaa63e",.68],
      wall:["#ec9d35",.42], fluid:["#238f9e",.41], parcel:["#fff3b0",.24],
    };
    this.materials = new Map(Object.entries(materials).map(([id,[color,roughness]]) =>
      [id,new THREE.MeshStandardMaterial({color,roughness,side:THREE.DoubleSide,emissive:color,emissiveIntensity:.035,vertexColors:id==="front"})]));
    const meshOf = (id, geometry) => {
      const mesh = new THREE.Mesh(geometry,this.materials.get(id));
      mesh.userData.pick = part(id);
      return mesh;
    };
    const draw = (group, build) => {
      const pieces = new Map();
      const scenery = build((id,geometry) => {
        if (!pieces.has(id)) pieces.set(id,[]);
        pieces.get(id).push(geometry);
      });
      for (const [id,geometries] of pieces) {
        group.add(meshOf(id,mergeGeometries(geometries)));
        geometries.forEach(geometry => geometry.dispose());
      }
      if (scenery) group.add(scenery);
      return scenery;
    };
    this.plate = draw(this.network,drawNetwork);
    draw(this.cutaway,drawCutaway);
    this.parcel = meshOf("parcel",new THREE.IcosahedronGeometry(.19,2));
    this.cutaway.add(this.parcel);
    this.arrows = new THREE.Group();
    this.cutaway.add(this.arrows);
    for (const x of [-2.2,-1.12,0,1.12,2.2]) {
      const arrow = new THREE.ArrowHelper(point(1,0,0),point(x,-.09,.23),.68,0xb4edf0,.22,.11);
      arrow.traverse(child => child.userData.unpickable = true);
      this.arrows.add(arrow);
    }
    this.anchor = new Map([
      ["veins",point(-2.1,.52,.03)],["web",point(-1.8,.17,-1.68)],["front",point(2.83,.13,2.15)],
      ["wall",point(1.55,1.0,-.04)],["fluid",point(-1.95,-.25,.74)],["parcel",this.parcel.position],
    ]);
    this.bounds = { network:new THREE.Box3().setFromObject(this.network),vein:new THREE.Box3().setFromObject(this.cutaway) };
    // Fit the dish's visible rim so its empty bounding-box corners take up no screen space.
    this.rim = Array.from({length:48},(_,i) => {
      const angle=i*Math.PI/24;
      return point(this.plate.position.x+this.plate.scale.x*Math.cos(angle),.25,this.plate.scale.z*Math.sin(angle));
    });
    this.sync();
  }
  get pickRoots() { return [this.level === "network" ? this.network : this.cutaway]; }
  get visibleParts() { return this.level === "network" ? ["veins","web","front"] : ["wall","fluid","parcel"]; }
  activate() {
    this.active = true;
    this.stage.scene.add(this.root);
    this.stage.dress?.({rich:true,filmic:false,contact:false});
    this.stage.rig.limits = {minDistance:3.2,maxDistance:50,minPolar:.08,maxPolar:Math.PI-.1};
    this.applyPalette(this.stage.palette);
    this.frame();
    this.names();
  }
  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.stage.dress?.({rich:false});
    this.labels.clear();
  }
  dispose() {
    this.cutaway.remove(this.arrows);
    for (const arrow of this.arrows.children) {
      // Arrow helpers share their geometry across scenes.
      arrow.line.material.dispose();
      arrow.cone.material.dispose();
    }
    const held = new Set();
    this.root.traverse(object => {
      if (object.geometry) held.add(object.geometry);
      if (object.material) held.add(object.material);
    });
    for (const resource of held) resource.dispose();
  }
  applyPalette({dark} = {}) {
    this.plate.material.color.set(dark ? "#383a35" : "#a1a592");
    this.stage.invalidate();
  }
  frame() {
    const {width,height,camera,rig} = this.stage;
    const {left=0,right=0,bottom=0} = this.stage.insets || {};
    const viewHeight = Math.max(160,height-bottom), viewWidth = Math.max(160,width-left-right);
    const phone = width < 700, network = this.level === "network";
    this.room = [width,height,left,right,bottom].join("/");
    const fov = 2*Math.atan(Math.tan(camera.fov*Math.PI/360)*viewHeight/height)*180/Math.PI;
    rig.setView(fitView(this.bounds[this.level],{fov,aspect:viewWidth/viewHeight,azimuth:phone ? 1.15 : .09,
      polar:network ? .47 : .98,margin:phone ? .12 : .16,points:network ? this.rim : null}));
  }
  names() {
    this.labels.clear();
    for (const id of this.visibleParts) {
      this.labels.add({id:part(id),text:detail[id][0],anchor:this.anchor.get(id),priority:700,lift:8});
    }
  }
  levels() { return this.entry.levels.map(level => ({...level,active:level.id===this.level})); }
  setLevel(id) {
    if (!this.bounds[id] || this.level === id) return;
    this.level = id;
    this.setSelection(null);
    this.sync();
    if (this.active) { this.names(); this.frame(); }
    this.onMode?.();
    this.stage.invalidate();
  }
  setMode(value) {
    this.flow = value === "flow" && !this.stage.reducedMotion ? "flow" : "rest";
    this.onChrome?.();
    this.stage.invalidate();
  }
  reverse() {
    this.phase = Math.PI - this.phase;
    this.sync();
    this.stage.invalidate();
  }
  sync() {
    this.network.visible = this.level === "network";
    this.cutaway.visible = !this.network.visible;
    this.parcel.position.set(Math.sin(this.phase)*2.48, .018, .26);
    const sign = Math.cos(this.phase) >= 0 ? 1 : -1;
    for (const arrow of this.arrows.children) arrow.setDirection(point(sign,0,0));
  }
  update(dt) {
    const {width,height,insets={}} = this.stage;
    if ([width,height,insets.left || 0,insets.right || 0,insets.bottom || 0].join("/") !== this.room) this.frame();
    if (this.level !== "vein" || this.flow !== "flow" || this.stage.reducedMotion) return false;
    this.phase += Math.min(60,dt) * .0016;
    this.sync();
    return true;
  }
  has(id) { return this.visibleParts.some(key => part(key) === id); }
  sections() { return [{label:this.level === "network" ? "Plasmodium" : "Inside a vein",
    entities:this.visibleParts.map(key => this.describe(part(key)))}]; }
  setSelection(id) {
    for (const [key,material] of this.materials) material.emissiveIntensity = part(key) === id ? .46 : .055;
    this.stage.invalidate();
  }
  describe(id) {
    const key = String(id).slice("physarum:".length);
    if (!this.has(id)) return null;
    const [label,plain] = detail[key];
    return {id,label,plain,kind:"illustrated anatomy",eyebrow:"Physarum · 3D illustration",
      doors:key==="veins" ? [{lens:"engine",select:this.entry.view.engine_part,label:"Open the Engine catalogue entry"}] :
        key==="wall" ? [
          {lens:"machines",select:"machine:myosin-ii-regulatory-domain",label:"Inspect the myosin II regulatory domain"},
          {lens:"proteins",show:"own",find:"P02576",label:"Look up plasmodial actin"},
        ] : []};
  }
  chrome() {
    const show = (lens, detail) => emit(this.stage.canvas,"cells-door",{lens,...detail});
    const button = (label, action, key) => h("button",{type:"button",class:"link-button",dataset:{physarum:key},onclick:action},label);
    return {
      caveat:"Anatomy and flow illustration · schematic dimensions",
      card:{heading:this.entry.label,text:this.level==="network" ? this.entry.plain : "Follow one parcel as cytoplasm changes direction.",
        modes:this.level==="vein" && !this.stage.reducedMotion ?
          {label:"Shuttle streaming",options:[["rest","Paused"],["flow","Animate illustration"]],active:this.flow} : null,
        own:()=>[h("div",{class:"physarum-links"},
          this.level==="vein" ? button("Reverse arrows",()=>this.reverse(),"reverse") : null,
          button("Physarum proteins",()=>show("proteins",{show:"own"}),"proteins"),
          button("Molecular machines",()=>show("machines",{}),"machines"),
          button("Engine catalogue",()=>show("engine",{select:this.entry.view.engine_part}),"engine"))],
        sources:this.entry.modelled.record},
      legend:false,
    };
  }
}

registerEntryView("physarum",{
  label:"Physarum",short:"Physarum",
  make:(stage,model,labels,{entry}) => new PhysarumLens(stage,labels,entry),
  styles:{shadow:".physarum-links {display:flex; flex-wrap:wrap; gap:5px 12px; padding-block:4px} @media (max-width:760px) {.physarum-links button {min-height:40px}}"},
});
