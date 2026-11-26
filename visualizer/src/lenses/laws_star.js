import { LawsAtlasLens, makeLawsView as classicLaws } from "./laws_atlas.js";
import { NEIGHBOURS_PER_LAYER } from "./laws_atlas_scene.js";
import { engineId, pageId } from "./laws_data.js";
import { partsOf } from "./laws_connections.js";
import { StarLight } from "./laws_starlight.js";
import { drawStars, starConnection, starLayout, starVerb } from "./laws_star_scene.js";
import { starConsole, starControls } from "./laws_star_controls.js";
import { h } from "../ui/dom.js";

export function makeLawsView(stage, model, labels) {
  const layout = new URLSearchParams(globalThis.location?.search).get("lawLayout");
  return ["shelves","atlas"].includes(layout) ? classicLaws(stage,model,labels) : new LawsStarLens(stage,model,labels);
}

const firstRelation = rows => Object.keys(starVerb).find(verb => rows.some(e => e.verb === verb)) || null;

export class LawsStarLens extends LawsAtlasLens {
  constructor(stage, model, labels) {
    super(stage,model,labels);
    this.map = starLayout(this.library);
    this.light = new StarLight();
    this.primary = null;
    this.showFamilyRoutes = false;
    this.path = [];
    this.terminal = false;
    this.matrixPage = 0;
    this.matrixGroup = -1;
    this.sweepTime = null;
  }
  activate() {
    this.frame = this.stage.canvas.closest(".frame");
    this.frame.classList.add("laws-space");
    this.console = h("div",{class:"star-overlay"});
    this.frame.append(this.console);
    this.stage.scene.add(this.light.root);
    super.activate();
    this.syncInsets();
    this.refreshConsole();
  }
  deactivate() {
    this.stopEffects();
    if (this.stage.rig.flight?.path) this.stage.rig.flight = null;
    this.stage.scene.remove(this.light.root);
    this.frame?.classList.remove("laws-space");
    this.console?.remove();
    this.console = null;
    super.deactivate();
  }
  dispose() { this.light.dispose(); super.dispose(); }
  stopEffects() {
    this.sweepTime = null;
    this.light.glow.uniforms.sweep.value = -3;
    this.light.pulse.visible = false;
  }
  drawScene(d) { drawStars(d,this); }
  visibleEdges() {
    return this.traceRows.filter(e=>e.verb===this.relation).slice(this.page*NEIGHBOURS_PER_LAYER,(this.page+1)*NEIGHBOURS_PER_LAYER);
  }
  traceLayers() {
    const visible = this.visibleEdges();
    return Object.fromEntries(["models","pieces","fields"].map(layer => [layer, visible.filter(e=>e.layer===layer)]));
  }
  examplePiece() {
    const members = this.graph.members.get(this.primary);
    const pieces = this.filtered().filter(p=>(!members || members.has(p.id)) && p.declared);
    return pieces.find(p=>p.id==="cells.operator.site_occupant_replacement@1") || pieces.find(p=>this.graph.requirements(p).length) || pieces[0];
  }
  familyRoutes() {
    const members = this.graph.members.get(this.primary);
    return this.graph.familyRoutes(this.family, this.filtered().filter(p => !members || members.has(p.id)));
  }
  showRoute(source, verb) {
    this.tracePiece(source.id);
    this.setRelation(verb);
  }
  overviewCount() {
    const members = this.graph.members.get(this.primary);
    const pieces = this.filtered().filter(p=>!members || members.has(p.id));
    return {pieces:pieces.length, families:new Set(pieces.map(p=>p.family)).size};
  }
  syncInsets() {
    if (!this.console) return;
    const {left=0,right=0,bottom=0} = this.stage.insets || {};
    this.console.style.setProperty("--star-left", left+"px");
    this.console.style.setProperty("--star-right", right+"px");
    this.console.style.setProperty("--star-bottom", bottom+"px");
  }
  roomChanged() { super.roomChanged(); this.syncInsets(); }
  fit(fly=true, box) {
    const bounds = this.mode==="wiring" && this.traceBox ? this.traceBox : this.familyBounds || box || this.focusBox || this.drawing.bounds;
    // Keep the heading the visitor chose when following a connection.
    const aimed = this.mode==="wiring" && this.path.length;
    const orientation = aimed ? {azimuth:this.stage.rig.azimuth,polar:this.stage.rig.polar,margin:.23} :
      {azimuth:this.portrait ? 1.46 : .15,polar:this.portrait ? .48 : .78,margin:this.mode==="wiring" ? .24 : .13};
    const view = this.framedView(bounds,orientation);
    if (fly) this.stage.rig.flyTo(view,650);
    else this.stage.rig.setView(view);
  }
  update(dt) {
    super.update();
    this.light.update(this.stage);
    if (this.stage.reducedMotion || this.stage.rig.instant) this.stopEffects();
    const flight = this.stage.rig.flight;
    this.light.pulse.visible = Boolean(flight?.path);
    if (flight?.path) flight.path.getPoint(flight.progress || 0,this.light.pulse.position);
    if (this.sweepTime === null) return Boolean(flight?.path);
    this.sweepTime += dt;
    this.light.glow.uniforms.sweep.value = -.18 + this.sweepTime/850;
    if (this.sweepTime >= 1200) this.stopEffects();
    return true;
  }
  setPrimary(id) {
    if (this.mode==="compare") { this.matrixPage=0; super.setPrimary(id); return; }
    this.primary = this.library.frame(id)?.id || null;
    this.clearPanel();
    this.stopEffects();
    if (this.primary && !this.stage.reducedMotion && !this.stage.rig.instant) this.sweepTime=0;
    this.notice({fit:this.showFamilyRoutes});
  }
  openMatrix() {
    const frames=this.library.frames;
    if (!this.primary) {this.matrixPreviousModel=null; this.primary=this.defaultModel||frames[0]?.id;}
    else this.matrixPreviousModel=this.primary;
    const partner=frames.find(f=>f.id!==this.primary && (this.graph.members.get(f.id)?.size||0)>0) || frames.find(f=>f.id!==this.primary);
    if (partner) this.compareWith(partner.id);
  }
  compareWith(id) {
    if (!this.library.frame(id) || id===this.primary) return;
    this.stopEffects();
    this.matrixPage=0; this.matrixGroup=-1;
    super.compareWith(id);
  }
  setMark(id) {
    this.showFamilyRoutes=false;
    super.setMark(id);
    this.refreshConsole();
  }
  enterTrace(piece, returnSelection=this.selected) {
    super.enterTrace(piece,returnSelection);
    this.trail=[]; this.path=[]; this.terminal=false;
    this.relation=firstRelation(this.traceRows);
    this.stopEffects();
  }
  follow(id) {
    const link=this.links.get(id);
    if (!link || this.mode!=="wiring" || this.terminal) return false;
    this.clearPanel();
    const step = {from:this.trace, edge:link.edge, curve:link.curve, page:this.page};
    this.path.push(step);
    const peer = this.library.piece(engineId(id));
    if (peer) this.atPiece(peer);
    else this.terminal=true;
    this.stopEffects();
    this.notice();
    const rig = this.stage.rig;
    const view=this.framedView(this.traceBox,{azimuth:rig.azimuth,polar:rig.polar,margin:.23});
    rig.flyTo(view,1000,step.curve);
    return true;
  }
  atPiece(p) {
    this.trace=p.id; this.traceRows=this.graph.neighbours(p);
    this.relation=firstRelation(this.traceRows); this.page=0; this.terminal=false;
  }
  jumpStop(index) {
    if (!Number.isInteger(index) || index<0 || index>=this.path.length) return;
    const departure=this.path[index];
    this.clearPanel();
    this.path.length=index;
    this.atPiece(this.library.piece(departure.from));
    this.relation=departure.edge.verb; this.page=departure.page;
    this.notice({fit:true});
  }
  setRelation(verb) {
    if (!this.traceRows.some(e=>e.verb===verb)) return;
    this.relation=verb; this.page=0;
    this.notice({fit:true});
  }
  openOnMap(id) {
    if (!id) return false;
    if (this.mode==="wiring") {
      if (this.follow(id)) return true;
      const stop = this.path.findIndex(s=>pageId(s.from)===id);
      if (stop!==-1) {this.jumpStop(stop);return true;}
      if (this.terminal && this.path.at(-1).edge.id===id) {this.selectOnPage(id);return true;}
    }
    if (this.mode==="atlas" && partsOf(id)[0]==="family") {this.setMark(partsOf(id)[1]);return true;}
    return super.openOnMap(id);
  }
  back() {
    if (this.mode==="wiring" && this.path.length) {this.jumpStop(this.path.length-1);return true;}
    const comparing=this.mode==="compare";
    if (comparing && this.matrixPreviousModel!==undefined) {
      this.primary=this.matrixPreviousModel;
      this.matrixPreviousModel=undefined;
    }
    this.terminal=false;
    const changed=super.back();
    this.refreshConsole();
    return changed;
  }
  overview() {
    if (this.mode==="wiring") {
      this.path=[];this.terminal=false;this.trail=[];
      super.back();
    }
    if (this.mode==="compare") this.back();
    this.showFamilyRoutes=false;
    this.family=null;this.nearFamily=null;this.focusBox=null;
    this.clearPanel();this.notice({fit:true});
  }
  address() {
    const base=super.address();
    const trail=this.mode==="wiring" ? this.path.slice(-40) : [];
    return {...base,lawModel:this.primary,lawRelation:this.mode==="wiring" ? this.relation : null,
      lawTrail:trail.length ? JSON.stringify([trail[0].from,...trail.map(s=>[s.edge.verb,s.edge.id])]) : null};
  }
  restore(query) {
    super.restore(query);
    if (this.mode!=="wiring") return;
    const trace=this.trace;
    let saved;
    try {saved=JSON.parse(query.get("lawTrail"));} catch {}
    // A shared path is replayed against this revision's actual declarations.
    if (Array.isArray(saved) && saved.length>=2 && saved.length<=41) {
      let p=this.library.piece(typeof saved[0]==="string" ? saved[0] : null), terminal=false;
      const steps=[];
      for (const item of saved.slice(1)) {
        if (!p || terminal || !Array.isArray(item)) break;
        const edges=this.graph.neighbours(p).filter(e=>e.verb===item[0]);
        const endpoint=this.canonical(item[1]);
        const i=edges.findIndex(e=>e.id && e.id===endpoint);
        if (i<0) break;
        const page=Math.floor(i/NEIGHBOURS_PER_LAYER), offset=i%NEIGHBOURS_PER_LAYER;
        const curve=starConnection(this.map,p.id,edges[i],offset,Math.min(NEIGHBOURS_PER_LAYER,edges.length-page*NEIGHBOURS_PER_LAYER));
        steps.push({from:p.id,edge:edges[i],curve,page});
        const peer=this.library.piece(engineId(edges[i].id));
        if (peer) p=peer; else terminal=true;
      }
      if (steps.length===saved.length-1 && p?.id===trace) {this.path=steps;this.terminal=terminal;}
    }
    const verb=query.get("lawRelation");
    if (this.traceRows.some(e=>e.verb===verb)) this.relation=verb;
    this.notice({fit:true,address:false});
  }
  refreshConsole() {
    if (!this.console) return;
    const active=this.console.getRootNode().activeElement;
    const key=this.console.contains(active) && active.getAttributeNames().find(name=>name.startsWith("data-"));
    const entered=this.console.dataset.mode !== this.mode;
    this.console.dataset.mode=this.mode;
    this.console.replaceChildren(starConsole(this));
    if (entered && this.mode==="compare") this.console.firstElementChild.classList.add("star-matrix-enter");
    if (key) {
      const same=this.console.querySelector("["+key+"="+CSS.escape(active.getAttribute(key))+"]");
      const next=same && !same.disabled ? same : this.console.querySelector('[aria-current="step"],button:not(:disabled)');
      next?.focus({preventScroll:true});
    }
    const crumbs=this.console.querySelector(".star-breadcrumbs");
    if (crumbs) crumbs.scrollLeft=crumbs.scrollWidth;
    this.syncInsets();
  }
  notice(options) { super.notice(options); this.refreshConsole(); }
  chrome() {
    const spec=super.chrome();
    spec.card.heading={atlas:"Laws star atlas",wiring:"Connection trace",compare:"Compare models"}[this.mode];
    spec.card.own=()=>[starControls(this)];
    if (this.mode==="atlas") {
      const n=this.overviewCount();
      spec.legend={title:"Star atlas",items:[
        ["laws-atlas-island","Family pod",this.library.families.length],
        ["star-piece",this.primary?"Highlighted pieces":"Catalogue pieces",n.pieces],
        ["star-design","Open ring · design note",this.library.counts().where.design],
      ].map(([swatch,label,count])=>({swatch,label,count,passive:true})),note:{text:"Each star sits above its family’s pod."}};
      if (spec.back) spec.back="Whole atlas";
    } else if (this.mode==="wiring") {
      const last=this.path.at(-1);
      spec.back=last?"Previous stop":this.fromTrace==="compare"?"Model matrix":"Star atlas";
      spec.legend={title:"Flight path",items:[
        {swatch:"laws-atlas-"+(this.relation||"requires"),label:this.relation ? starVerb[this.relation] : "Connections",count:this.terminal?0:this.visibleEdges().length,passive:true},
        {swatch:"star-trail",label:"Followed connections",count:this.path.length,passive:true},
      ],note:{text:"Read each link from the selected piece toward its labelled neighbour."}};
    } else spec.back="Star atlas";
    return spec;
  }
}
