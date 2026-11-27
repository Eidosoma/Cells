import * as THREE from "../three.js";
import { h, emit } from "../ui/dom.js";
import { registerEntryView } from "../ui/entry_views.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { enrich } from "../core/materials.js";
import { fitView } from "./laws_marks.js";

import { drawNetwork, drawCutaway, networkAnchors, streamPoint } from "./parts/physarum_anatomy.js";
import { lightSpecimen, point, turn } from "./parts/illustration.js";
import { seeded } from "./parts/geometry.js";
const part = id => "physarum:" + id;
const detail = {
  veins: ["Main veins", "Thick tubes link growing regions of the plasmodium. Their contractile walls drive back-and-forth flow."],
  web: ["Fine network", "Small connected tubes branch from larger veins and link adjacent routes."],
  front: ["Advancing fan", "The thin, spreading edge is part of the same multinucleate cell."],
  wall: ["Contractile wall", "The outer gel contains the actomyosin system. Contraction changes the tube cross-section and drives fluid motion."],
  fluid: ["Streaming cytoplasm", "Pale granules trace the streaming endoplasm. Follow the gold parcel or reverse the arrows to compare directions."],
  parcel: ["Material parcel", "Follow this same marker through a reversal. Its location is the moving quantity in this Lagrangian illustration."],
};

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
      veins: ["#f5bb36",.35], web:["#e8ab34",.39], front:["#ffffff",.49],
      wall:["#ffffff",.43], fluid:["#ffffff",.31], parcel:["#ffcb52",.22],
    };
    this.materials = new Map();
    for (const [id,[color,roughness]] of Object.entries(materials)) {
      const painted = ["front","wall","fluid"].includes(id);
      const emissive = painted ? (id === "fluid" ? "#4f9b8f" : "#c58924") : color;
      const material = new THREE.MeshStandardMaterial({color, roughness, emissive,
        side:THREE.DoubleSide, emissiveIntensity:.035, vertexColors:painted});
      if (stage.numbers && id !== "parcel") {
        enrich(material,stage.numbers,{rim:.095,thin:id==="front" ? .35 : .1,texture:"grain",unit:.31});
      }
      this.materials.set(id,material);
    }
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
    // A slight change in calibre makes the contractile gel visible during the
    // illustration. Its resting geometry and the fluid paths share the tube axis.
    this.wall = this.cutaway.children.find(mesh => mesh.userData.pick === part("wall"));
    const position = this.wall.geometry.attributes.position;
    const offsets = new Float32Array(position.count*3);
    for (let i=0; i<position.count; i++) {
      const t=(position.getX(i)+3.5)/7, amplitude=.085*Math.sin(t*turn);
      offsets[i*3+1]=(position.getY(i)-.12*Math.sin(t*turn))*amplitude;
      offsets[i*3+2]=position.getZ(i)*amplitude;
    }
    this.wall.geometry.morphTargetsRelative = true;
    this.wall.geometry.morphAttributes.position = [new THREE.BufferAttribute(offsets,3)];
    this.wall.updateMorphTargets();
    this.parcel = meshOf("parcel",new THREE.IcosahedronGeometry(.19,2));
    this.cutaway.add(this.parcel);
    const random = seeded(6192);
    this.tracers = Array.from({length:52}, () => {
      const offset = (random()-.5)*5.3;
      const radial = (random()-.5)*1.3;
      return {offset, radial, travel:.27+random()*.46, size:.018+random()*.023, depth:.18-.33*radial**2};
    });
    this.grains = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),
      new THREE.MeshStandardMaterial({color:"#c1e5c6",roughness:.4}), this.tracers.length);
    this.grains.userData.pick = part("fluid");
    this.grains.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.grains.frustumCulled = false;
    this.stamp = new THREE.Object3D();
    this.cutaway.add(this.grains);
    this.arrows = new THREE.Group();
    this.cutaway.add(this.arrows);
    for (const x of [-1.95,0,1.95]) {
      const arrow = new THREE.ArrowHelper(point(1,0,0),point(x,.25,.49),.54,0x7bbeb7,.15,.08);
      arrow.traverse(child => child.userData.unpickable = true);
      this.arrows.add(arrow);
    }
    this.anchor = new Map([
      ...Object.entries(networkAnchors),
      ["wall",point(1.85,.85,-.54)],["fluid",streamPoint(-2.2,.24,.09)],["parcel",this.parcel.position],
    ]);
    this.bounds = { network:new THREE.Box3().setFromObject(this.network),vein:new THREE.Box3().setFromObject(this.cutaway) };
    const vertices = this.plate.geometry.attributes.position;
    this.rim = Array.from({length:221}, (_,i) => point().fromBufferAttribute(vertices,vertices.count-221+i));
    this.sync();
  }
  get pickRoots() { return [this.level === "network" ? this.network : this.cutaway]; }
  get visibleParts() { return this.level === "network" ? ["veins","web","front"] : ["wall","fluid","parcel"]; }
  activate() {
    this.active = true;
    this.stopLook ??= this.stage.look?.onChange?.(() => { if (this.active) lightSpecimen(this); });
    this.stage.scene.add(this.root);
    this.stage.dress?.({rich:true,filmic:true,exposure:1.06,contact:true,reach:.15,shade:.33});
    this.stage.rig.limits = {minDistance:3.2,maxDistance:50,minPolar:.08,maxPolar:Math.PI-.1};
    this.applyPalette(this.stage.palette);
    this.frame();
    this.names();
  }
  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.stage.dress?.({rich:false});
    this.stage.scene.environment = null;
    this.stage.applyPalette?.();
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
    this.stopLook?.();
    this.studio?.dispose();
    this.root.traverse(object => {
      if (object.isInstancedMesh) object.dispose();
      if (object.geometry) held.add(object.geometry);
      if (object.material) held.add(object.material);
    });
    for (const resource of held) resource.dispose();
  }
  applyPalette({dark} = {}) {
    if (this.active) lightSpecimen(this);
    this.plate.material.color.set(dark ? "#d0c6b9" : "#ffffff");
    this.stage.invalidate();
  }
  frame() {
    const {width,height,camera,rig} = this.stage;
    const {left=0,right=0,bottom=0} = this.stage.insets || {};
    const viewHeight = Math.max(160,height-bottom), viewWidth = Math.max(160,width-left-right);
    const phone = width < 700, network = this.level === "network";
    const rail = width > 760 && !right ? 166 : 0;
    this.room = [width,height,left,right,bottom].join("/");
    const fov = 2*Math.atan(Math.tan(camera.fov*Math.PI/360)*viewHeight/height)*180/Math.PI;
    const view = fitView(this.bounds[this.level],{fov,aspect:(viewWidth-rail)/viewHeight,
      azimuth:phone ? (network ? 1.22 : .58) : (network ? -.12 : -.33), polar:network ? .51 : 1.02,
      margin:phone ? .10 : .11,points:network ? this.rim : null});
    const across = point(Math.cos(view.azimuth),0,-Math.sin(view.azimuth));
    view.target.addScaledVector(across,rail*view.distance*Math.tan(camera.fov*Math.PI/360)/height);
    rig.setView(view);
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
    const displacement = Math.sin(this.phase);
    this.wall.morphTargetInfluences[0] = displacement;
    this.parcel.position.copy(streamPoint(displacement*2.48, -.19, .32));
    this.tracers.forEach(({offset, radial, travel, size, depth}, index) => {
      this.stamp.position.copy(streamPoint(offset+travel*displacement,radial,depth));
      this.stamp.scale.set(size*1.5,size,size);
      this.stamp.updateMatrix();
      this.grains.setMatrixAt(index,this.stamp.matrix);
    });
    this.grains.instanceMatrix.needsUpdate = true;
    this.grains.boundingSphere = null;
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
        key==="fluid" ? [{lens:"machines",select:"organelle:mitochondrion",label:"Inspect a plasmodial mitochondrion"}] :
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
      card:{heading:this.entry.label,text:this.level==="network" ? this.entry.plain : "Follow the gold parcel through the vein. Animate shuttle streaming to see it reverse with the surrounding granules.",
        modes:this.level==="vein" && !this.stage.reducedMotion ?
          {label:"Shuttle streaming",options:[["rest","Paused"],["flow","Animate illustration"]],active:this.flow} : null,
        own:()=>[h("div",{class:"physarum-links"},
          this.level==="vein" ? button("Reverse arrows",()=>this.reverse(),"reverse") : null,
          button("Physarum proteins",()=>show("proteins",{show:"own"}),"proteins"),
          button("Organelle shelf",()=>show("machines",{select:"organelle:nucleus"}),"shelf"),
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
