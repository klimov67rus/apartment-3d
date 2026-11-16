import './style.css';
import planScale from '../../artifacts/plan-door-scale/scale.json';
import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {PointerLockControls} from 'three/addons/controls/PointerLockControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {parseApartment,area,type Apartment} from './model';
import {buildApartment,disposeApartment} from './geometry';
const $=<E extends HTMLElement>(id:string)=>document.getElementById(id) as E;
const message=(s:string)=>{$('message').textContent=s};
const viewport=$('viewport'), editor=$<HTMLTextAreaElement>('json');
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;viewport.append(renderer.domElement);
const scene=new T.Scene();scene.background=new T.Color(0xe7e9e2);
const camera=new T.PerspectiveCamera(45,1,.05,2000);
const orbit=new OrbitControls(camera,renderer.domElement);orbit.enableDamping=true;orbit.maxPolarAngle=Math.PI/2-.01;
const walk=new PointerLockControls(camera,renderer.domElement);
scene.add(new T.HemisphereLight(0xffffff,0x8b9986,2.7));const sun=new T.DirectionalLight(0xfff3dc,3);sun.position.set(6,14,8);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);scene.add(sun);
let root:T.Group|undefined, current:Apartment|undefined, mode='orbit', center=new T.Vector3(), span=10;
let hasPlan=true, showPlan=true;
let planTexture=new T.TextureLoader().load('/examples/source-plan.jpg',undefined,undefined,()=>message('Не удалось загрузить исходный план'));planTexture.colorSpace=T.SRGBColorSpace;
let planWidth=1052*planScale.metersPerPixel, planHeight=1162*planScale.metersPerPixel;
function showUnderlay() {
 if(!root)return;root.traverse(o=>{if(o.name==='room-floor')o.visible=!hasPlan||!showPlan;if(o.name==='source-plan')o.visible=hasPlan&&showPlan});
 $('underlay').hidden=!hasPlan;$('underlay').setAttribute('aria-pressed',String(showPlan));$('underlay').textContent=`Исходный план: ${showPlan?'включён':'выключен'}`;
}
$('underlay').onclick=()=>{showPlan=!showPlan;showUnderlay()};
const cache=new Map<string,Promise<T.Group>>(), loader=new GLTFLoader();
async function attachFurniture(a:Apartment,target:T.Group) {
 for(const f of a.furniture) {
  const url=a.models[f.modelId];if(!cache.has(url)) cache.set(url,loader.loadAsync(url).then(g=>g.scene).catch(e=>{cache.delete(url);throw e}));
  try {const template=await cache.get(url)!;if(root!==target)return;const model=template.clone(true);model.traverse(o=>{if(o instanceof T.Mesh){o.geometry=o.geometry.clone();o.material=Array.isArray(o.material)?o.material.map(m=>m.clone()):o.material.clone()}});model.position.set(f.position[0],0,f.position[1]);model.rotation.y=f.rotation;target.add(model)} catch(e){if(root===target) message(`Геометрия построена; модель ${f.modelId} не загружена: ${String(e)}`)}
 }
}
function setMode(next:string) {
 mode=next;if(walk.isLocked)walk.unlock();orbit.enabled=next!=='walk';orbit.enableRotate=next!=='top';
 if(next==='walk') {const r=current?.rooms[0];if(r){const s=new T.Shape(r.polygon.map(([x,y])=>new T.Vector2(x,y)));const g=new T.ShapeGeometry(s);const p=g.getAttribute('position');const ix=g.index!;camera.position.set((p.getX(ix.getX(0))+p.getX(ix.getX(1))+p.getX(ix.getX(2)))/3,1.65,(p.getY(ix.getX(0))+p.getY(ix.getX(1))+p.getY(ix.getX(2)))/3);g.dispose()}camera.lookAt(camera.position.clone().add(new T.Vector3(0,0,-1)));}
 else {orbit.target.copy(center);camera.position.copy(center).add(next==='top'?new T.Vector3(0,span*1.65,.001):new T.Vector3(span,span*1.05,span));camera.lookAt(center);orbit.update()}
 for(const id of ['orbit','top','walk'])$(id).setAttribute('aria-pressed',String(id===next));
 $('mode').textContent=next==='top'?'ПЛАН':next==='walk'?'ПРОГУЛКА':'ОБЪЁМ';
 $('hint').textContent=next==='walk'?'Нажмите на сцену · WASD / стрелки — движение · мышь — обзор · Esc — курсор. Свободная камера без столкновений.':'Мышь — вращение · колесо — масштаб · правая кнопка — сдвиг';
}
function apply(input:unknown, withPlan=hasPlan) {
 const a=parseApartment(input), next=buildApartment(a);
 if(withPlan){
  // Match the image plane to the estimated scale used by this preview.
  const plane=new T.Mesh(new T.PlaneGeometry(planWidth,planHeight),new T.MeshBasicMaterial({map:planTexture,side:T.DoubleSide}));
  plane.name='source-plan';plane.rotation.x=-Math.PI/2;plane.position.set(planWidth/2,-.02,planHeight/2);next.add(plane);
 }
 hasPlan=withPlan;
 if(root){scene.remove(root);disposeApartment(root)}root=next;current=a;scene.add(root);
 const bounds=new T.Box3().setFromObject(root);bounds.getCenter(center);center.y=0;const size=bounds.getSize(new T.Vector3());span=Math.max(size.x,size.z,3);camera.far=Math.max(2000,span*10);camera.updateProjectionMatrix();
 sun.position.copy(center).add(new T.Vector3(span,span*2,span));sun.target.position.copy(center);scene.add(sun.target);sun.shadow.camera.left=-span;sun.shadow.camera.right=span;sun.shadow.camera.top=span;sun.shadow.camera.bottom=-span;sun.shadow.camera.far=span*5;sun.shadow.camera.updateProjectionMatrix();
 showUnderlay();editor.value=JSON.stringify(a,null,2);$('name').textContent=a.name;$('stats').textContent=`${a.rooms.reduce((s,r)=>s+area(r.polygon),0).toFixed(1)} м² · ${a.rooms.length} помещения · ${a.walls.length} стен`;$('scale').textContent=`Масштаб: ${a.scale.source}`;$('uncertainty').textContent=a.uncertainties.join(' · ');message('');setMode('orbit');void attachFurniture(a,root);
}
for(const id of ['orbit','top','walk'])$(id).onclick=()=>{if(current)setMode(id)};
$('apply').onclick=()=>{try{apply(JSON.parse(editor.value))}catch(e){message(String(e))}};
$<HTMLInputElement>('file').onchange=async(e)=>{const file=(e.target as HTMLInputElement).files?.[0];if(file)try{editor.value=await file.text();apply(JSON.parse(editor.value),false)}catch(e){message(String(e))}};
$('export').onclick=()=>{try{const a=parseApartment(JSON.parse(editor.value));const url=URL.createObjectURL(new Blob([JSON.stringify(a,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='apartment.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){message(String(e))}};
$<HTMLInputElement>('image-file').onchange=async(e)=>{
 const input=e.target as HTMLInputElement, file=input.files?.[0];if(!file)return;
 if(!['image/jpeg','image/png'].includes(file.type)||file.size>15*1024*1024){message('Выберите JPG или PNG размером до 15 МиБ');input.value='';return}
 input.disabled=true;$('upload-status').textContent='Распознаём план…';message('');
 let texture:T.Texture|undefined;const url=URL.createObjectURL(file);
 try{
  const response=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':file.type},body:file});
  const data=response.headers.get('content-type')?.includes('application/json')?await response.json():{};if(!response.ok)throw new Error(data.error||'Сервис распознавания недоступен. Запустите mise run dev.');
  const apartment=parseApartment(data.apartment);
  if(!Number.isFinite(data.metersPerPixel)||data.metersPerPixel<=0||!Number.isInteger(data.image?.width)||!Number.isInteger(data.image?.height)||data.image.width<=0||data.image.height<=0)throw new Error('Некорректные параметры изображения');
  texture=await new T.TextureLoader().loadAsync(url);texture.colorSpace=T.SRGBColorSpace;
  const previous=planTexture, width=planWidth, height=planHeight;
  planTexture=texture;planWidth=data.image.width*data.metersPerPixel;planHeight=data.image.height*data.metersPerPixel;
  try{apartment.name=`Автоматическое превью: ${file.name}`;showPlan=true;apply(apartment,true)}catch(error){planTexture=previous;planWidth=width;planHeight=height;throw error}
  previous.dispose();texture=undefined;$('upload-status').textContent='План построен автоматически.';
 }catch(error){texture?.dispose();message(error instanceof TypeError ? 'Нет связи с сервисом распознавания. Проверьте, что запущен mise run dev.' : `Не удалось построить план: ${String(error)}`);$('upload-status').textContent=''}
 finally{URL.revokeObjectURL(url);input.disabled=false;input.value=''}
};
renderer.domElement.onclick=()=>{if(mode==='walk')void walk.lock()};
document.addEventListener('pointerlockerror',()=>message('Браузер отказал в захвате мыши. Повторите нажатие на сцену.'));
const keys=new Set<string>();window.addEventListener('keydown',e=>{if(walk.isLocked){if(e.code==='Escape')walk.unlock();else keys.add(e.code);e.preventDefault()}});window.addEventListener('keyup',e=>keys.delete(e.code));window.addEventListener('blur',()=>keys.clear());walk.addEventListener('unlock',()=>keys.clear());
new ResizeObserver(()=>{const {width,height}=viewport.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix()}).observe(viewport);
let last=performance.now();renderer.setAnimationLoop((now)=>{const dt=Math.min((now-last)/1000,.05);last=now;if(walk.isLocked){const x=Number(keys.has('KeyD')||keys.has('ArrowRight'))-Number(keys.has('KeyA')||keys.has('ArrowLeft'));const z=Number(keys.has('KeyW')||keys.has('ArrowUp'))-Number(keys.has('KeyS')||keys.has('ArrowDown'));const norm=Math.max(1,Math.hypot(x,z));walk.moveRight(x/norm*dt*2.5);walk.moveForward(z/norm*dt*2.5)}else if(mode!=='walk')orbit.update();renderer.render(scene,camera)});
fetch('/examples/plan-automatic.json').then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json()}).then(apply).catch(e=>message(String(e)));
