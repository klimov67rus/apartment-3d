"""Automatic image-to-preview pipeline; no review file is required."""
import json
import math
import statistics
from pathlib import Path
import shutil

import cv2
import numpy as np
from shapely.geometry import MultiPoint
from recognizer.walls import detect_walls
from recognizer.normalize import normalize
from recognizer.openings import detect
from recognizer.cli import validate


def estimate_scale(openings):
    widths = [math.dist(o['start'], o['end']) for o in openings if o['kind'] == 'door']
    widths = [w for w in widths if math.isfinite(w) and w > 0]
    if len(widths) < 2:
        return None
    median = statistics.median(widths)
    inliers = [w for w in widths if abs(w - median) <= median * .25]
    if len(inliers) < 2 or max(inliers) / min(inliers) > 1.5:
        return None
    return {'metersPerPixel': .8 / statistics.median(inliers), 'assumedDoorWidthMeters': .8,
            'doorWidthsPixels': widths, 'usedDoorWidthsPixels': inliers}


def generate(source, output):
    source, output = Path(source), Path(output)
    if output.exists(): raise FileExistsError(f'Output already exists: {output}')
    if not source.is_file(): raise ValueError(f'Image file not found: {source}')
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    walls, settings = detect_walls(image)
    if not walls: raise ValueError('No walls detected')
    pixels = {'version':'1.0','kind':'wall-candidates','units':'px','scale':{'status':'unknown','source':'No reference length supplied'},'image':{'file':source.name,'width':image.shape[1],'height':image.shape[0]},'reviewRequired':True,'settings':settings,'walls':walls,'uncertainties':['Automatic candidates; scale is unknown.']}
    normalized = normalize(pixels)
    openings = detect(normalized, image)
    # Use detected walls and all candidate gaps to estimate enclosed floor regions.
    mask=np.zeros(image.shape[:2],np.uint8)
    for w in normalized['walls']:
        cv2.line(mask,tuple(round(v) for v in w['start']),tuple(round(v) for v in w['end']),255,max(3,round(w['thickness'])))
    for o in openings['openings']:
        cv2.line(mask,tuple(round(v) for v in o['start']),tuple(round(v) for v in o['end']),255,max(3,settings['minThicknessPx']))
    # shortcut: small unrecognized breaks are closed heuristically; replace with a topology model for complex plans.
    k=max(3,settings['minThicknessPx']*3)|1
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((k,k),np.uint8))
    free=cv2.bitwise_not(mask)
    count, labels, stats, _=cv2.connectedComponentsWithStats(free)
    polygons=[]
    for index in range(1,count):
        x,y,w,h,area=stats[index]
        if x==0 or y==0 or x+w>=image.shape[1] or y+h>=image.shape[0] or area < image.shape[0]*image.shape[1]*.002: continue
        component=np.uint8(labels==index)*255
        contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if not contours: continue
        contour=max(contours,key=cv2.contourArea)
        polygon=cv2.approxPolyDP(contour,2,True).reshape(-1,2)
        if len(polygon)>=3: polygons.append(polygon.tolist())
    fallback=False
    if not polygons:
        hull=MultiPoint([p for w in walls for p in (w['start'],w['end'])]).convex_hull
        if hull.geom_type!='Polygon': raise ValueError('Cannot estimate a floor from detected walls')
        polygons=[list(map(list,hull.exterior.coords[:-1]))]; fallback=True
    estimate = estimate_scale(openings['openings'])
    if estimate is None:
        output.mkdir(parents=True,exist_ok=False)
        try:
            for name,data in [('walls-pixels.json',normalized),('openings-pixels.json',openings),('scale.json',{'status':'unknown','reason':'Недостаточно согласующихся распознанных дверей'})]:
                (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        except BaseException:
            shutil.rmtree(output); raise
        return {'units':'px','scale':{'status':'unknown','source':'Недостаточно согласующихся распознанных дверей'}}
    # shortcut: 0.8 m is an assumed door width, not a measured calibration.
    factor=estimate['metersPerPixel']
    def pt(p): return [round(float(v)*factor,5) for v in p]
    scene={'version':'1.0','name':f'Автоматическое превью: {source.name}', 'units':'m','scale':{'status':'estimated','source':f"ОЦЕНКА: дверь 0,8 м; {factor:.6g} м/px; фактический масштаб неизвестен"},'uncertainties':['Масштаб оценён по предполагаемой ширине двери 0,8 м; реальные размеры неизвестны.', 'Высоты и размеры проёмов заданы условно; стены, помещения и типы проёмов определены эвристически.', 'Неопределённые проёмы оставлены разрывами; автоматические ошибки возможны.'], 'walls':[], 'rooms':[], 'openings':[], 'furniture':[], 'models':{}}
    if fallback: scene['uncertainties'].append('Помещения не замкнулись: пол приблизительно построен по выпуклой оболочке стен.')
    for w in normalized['walls']:
        scene['walls'].append({'id':w['id'],'start':pt(w['start']),'end':pt(w['end']),'thickness':w['thickness']*factor,'height':2.7})
    for i,polygon in enumerate(polygons):
        scene['rooms'].append({'id':f'room{i+1}','name':f'Помещение {i+1}','polygon':[pt(p) for p in polygon]})
    for o in openings['openings']:
        if o['kind']=='unknown': continue
        start,end=pt(o['start']),pt(o['end']); width=math.dist(start,end)
        wallid='gap-'+o['id']
        scene['walls'].append({'id':wallid,'start':start,'end':end,'thickness':.16,'height':2.7})
        scene['openings'].append({'id':o['id'],'wallId':wallid,'kind':o['kind'],'offset':0,'width':width,'bottom':.9 if o['kind']=='window' else 0,'height':1.4 if o['kind']=='window' else 2.1})
    validate(scene)
    output.mkdir(parents=True,exist_ok=False)
    try:
        for name,data in [('walls-pixels.json',normalized),('openings-pixels.json',openings),('apartment-preview.json',scene),('scale.json',{'status':'estimated',**estimate})]:
            (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    except BaseException:
        shutil.rmtree(output); raise
    return scene
