import {test} from 'node:test';
import assert from 'node:assert/strict';
import sample from '../viewer/public/examples/apartment.json';
import {parseApartment, type Apartment} from '../viewer/src/model';
import {wallCells,buildApartment,disposeApartment} from '../viewer/src/geometry';
const data=()=>parseApartment(structuredClone(sample));
test('sample builds finite geometry with exact opening areas',()=>{
 const a=parseApartment(data());
 for(const w of a.walls){const holes=a.openings.filter(o=>o.wallId===w.id);const cells=wallCells(w,holes);assert.ok(Math.abs(cells.reduce((s,c)=>s+c.width*c.height,0)-(Math.hypot(w.end[0]-w.start[0],w.end[1]-w.start[1])*w.height-holes.reduce((s,o)=>s+o.width*o.height,0)))<1e-8)}
 const root=buildApartment(a);assert.ok(root.children.length>0);disposeApartment(root);
});
test('diagonal wall with vertically stacked windows',()=>{
 const w={id:'w',start:[0,0] as [number,number],end:[3,4] as [number,number],height:4,thickness:.2};
 const holes=[{id:'a',wallId:'w',kind:'window' as const,offset:1,width:2,bottom:.5,height:1},{id:'b',wallId:'w',kind:'window' as const,offset:1,width:2,bottom:2,height:1}];
 assert.equal(wallCells(w,holes).reduce((s,c)=>s+c.width*c.height,0),16);
});
test('reject invalid geometry and references',()=>{
 for(const mutate of [(a:Apartment)=>a.openings[0].offset=100,(a:Apartment)=>a.openings[0].wallId='missing',(a:Apartment)=>a.walls[0].end=a.walls[0].start,(a:Apartment)=>a.openings.push({...a.openings[0],id:'overlap'}),(a:Apartment)=>a.rooms[0].polygon=[[0,0],[4,4],[0,4],[4,0],[5,0]],(a:Apartment)=>a.walls[0].height=Infinity]){const a=data();mutate(a);assert.throws(()=>parseApartment(a))}
});
test('unknown scale is valid data but cannot become a metric scene',()=>{const a=data();a.units='px';a.scale.status='unknown';parseApartment(a);assert.throws(()=>buildApartment(a));a.units='m';assert.throws(()=>parseApartment(a))});
