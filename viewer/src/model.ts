import Ajv from 'ajv';
import schema from '../../schema/apartment.schema.json';
export type Point = [number, number];
export interface Wall { id:string; start:Point; end:Point; thickness:number; height:number }
export interface Opening { id:string; wallId:string; kind:'door'|'window'; offset:number; width:number; bottom:number; height:number }
export interface Apartment { version:'1.0'; name:string; units:'m'|'px'; scale:{status:'known'|'estimated'|'unknown';source:string}; uncertainties:string[]; walls:Wall[]; rooms:{id:string;name:string;polygon:Point[]}[]; openings:Opening[]; furniture:{id:string;modelId:string;position:Point;rotation:number}[]; models:Record<string,string> }
const validate = new Ajv({allErrors:true, strictNumbers:true}).compile<Apartment>(schema);
export const length = (w:Wall) => Math.hypot(w.end[0]-w.start[0],w.end[1]-w.start[1]);
export function area(p:Point[]) { return Math.abs(p.reduce((sum,a,i)=>{const b=p[(i+1)%p.length];return sum+a[0]*b[1]-b[0]*a[1]},0))/2 }
export function parseApartment(input:unknown):Apartment {
 if(!validate(input)) throw new Error(new Ajv().errorsText(validate.errors));
 const a=input;
 const ids=[...a.walls,...a.rooms,...a.openings,...a.furniture].map(x=>x.id);
 if(new Set(ids).size!==ids.length) throw new Error('ID объектов должны быть уникальны');
 for(const w of a.walls) if(length(w)<1e-6) throw new Error(`Нулевая стена ${w.id}`);
 for(const r of a.rooms) {
  if(area(r.polygon)<1e-8) throw new Error(`Нулевая площадь ${r.id}`);
  // shortcut: простые полигоны без отверстий; расширить контракт при поддержке внутренних дворов.
  const p=r.polygon;
  const cross=(a:Point,b:Point,c:Point)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const on=(a:Point,b:Point,c:Point)=>cross(a,b,c)===0&&c[0]>=Math.min(a[0],b[0])&&c[0]<=Math.max(a[0],b[0])&&c[1]>=Math.min(a[1],b[1])&&c[1]<=Math.max(a[1],b[1]);
  for(let i=0;i<p.length;i++) for(let j=i+1;j<p.length;j++) {
   if(j===i+1||(i===0&&j===p.length-1)) continue;
   const [a,b,c,d]=[p[i],p[(i+1)%p.length],p[j],p[(j+1)%p.length]];
   if((cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0)||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b)) throw new Error(`Самопересечение ${r.id}`);
  }
 }
 for(const o of a.openings) {
  const w=a.walls.find(w=>w.id===o.wallId);
  if(!w||o.offset+o.width>length(w)+1e-8||o.bottom+o.height>w.height+1e-8) throw new Error(`Проём ${o.id} выходит за стену`);
  if(o.kind==='door'&&o.bottom!==0) throw new Error(`Дверь ${o.id} должна начинаться от пола`);
  for(const b of a.openings) if(b!==o&&b.wallId===o.wallId&&o.offset<b.offset+b.width&&b.offset<o.offset+o.width&&o.bottom<b.bottom+b.height&&b.bottom<o.bottom+o.height) throw new Error(`Пересекающиеся проёмы ${o.id}, ${b.id}`);
 }
 for(const f of a.furniture) if(!a.models[f.modelId]) throw new Error(`Неизвестная модель ${f.modelId}`);
 return a;
}
