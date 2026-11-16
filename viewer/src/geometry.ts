import * as T from 'three';
import {length, type Wall, type Opening, type Apartment} from './model';
export function wallCells(w:Wall, openings:Opening[]) {
 const cuts=[...new Set([0,length(w),...openings.flatMap(o=>[o.offset,o.offset+o.width])])].sort((a,b)=>a-b);
 const cells:{x:number;y:number;width:number;height:number}[]=[];
 for(let i=0;i<cuts.length-1;i++) {
  const left=cuts[i], right=cuts[i+1]; let bottom=0;
  const holes=openings.filter(o=>o.offset<(left+right)/2&&o.offset+o.width>(left+right)/2).sort((a,b)=>a.bottom-b.bottom);
  for(const o of holes) {if(o.bottom>bottom) cells.push({x:left,y:bottom,width:right-left,height:o.bottom-bottom});bottom=o.bottom+o.height}
  if(bottom<w.height) cells.push({x:left,y:bottom,width:right-left,height:w.height-bottom});
 }
 return cells;
}
export function buildApartment(a:Apartment) {
 if(a.units!=='m'||a.scale.status==='unknown') throw new Error('Сначала откалибруйте масштаб: метрическая сцена недоступна');
 const root=new T.Group();root.name='apartment';
 const walls=new T.MeshStandardMaterial({color:0xe8e2d7,roughness:.9});
 const colors=[0xc6b69b,0x9aafa4,0xb5bac2];
 for(const [i,r] of a.rooms.entries()) {
  const shape=new T.Shape(r.polygon.map(([x,y])=>new T.Vector2(x,-y)));
  const floor=new T.Mesh(new T.ShapeGeometry(shape),new T.MeshStandardMaterial({color:colors[i%colors.length],side:T.DoubleSide,roughness:1}));
  floor.name='room-floor';floor.rotation.x=-Math.PI/2;floor.position.y=-.01;floor.receiveShadow=true;root.add(floor);
 }
 for(const w of a.walls) {
  const group=new T.Group();group.position.set(w.start[0],0,w.start[1]);group.rotation.y=-Math.atan2(w.end[1]-w.start[1],w.end[0]-w.start[0]);
  for(const c of wallCells(w,a.openings.filter(o=>o.wallId===w.id))) {
   const mesh=new T.Mesh(new T.BoxGeometry(c.width,c.height,w.thickness),walls);mesh.position.set(c.x+c.width/2,c.y+c.height/2,0);mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);
   const edge=new T.LineSegments(new T.EdgesGeometry(mesh.geometry),new T.LineBasicMaterial({color:0x8e897e,transparent:true,opacity:.25}));edge.position.copy(mesh.position);group.add(edge);
  }
  root.add(group);
 }
 return root;
}
export function disposeApartment(root:T.Group) {
 const materials=new Set<T.Material>();root.traverse(o=>{if(o instanceof T.Mesh||o instanceof T.LineSegments){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>materials.add(m))}});materials.forEach(m=>m.dispose());
}
