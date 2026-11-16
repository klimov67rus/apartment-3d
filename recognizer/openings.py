"""Propose openings from gaps between normalized wall segments."""
import json
import math
from pathlib import Path
import shutil

import cv2
import numpy as np
from shapely.geometry import LineString, MultiPoint, Point


def has_parallel_window_lines(edges, start, end, thickness):
    """Look for two long distinct parallel strokes inside a candidate gap."""
    horizontal = start[1] == end[1]
    along = 0 if horizontal else 1
    axis = 1 - along
    length = abs(end[along] - start[along])
    margin = max(8, round(thickness * 1.5))
    lo, hi = sorted((round(start[along]), round(end[along])))
    center = round(start[axis])
    if horizontal:
        x0, x1 = max(0,lo), min(edges.shape[1],hi+1)
        y0, y1 = max(0,center-margin), min(edges.shape[0],center+margin+1)
    else:
        x0, x1 = max(0,center-margin), min(edges.shape[1],center+margin+1)
        y0, y1 = max(0,lo), min(edges.shape[0],hi+1)
    if x1 <= x0 or y1 <= y0: return False
    lines=cv2.HoughLinesP(edges[y0:y1,x0:x1],1,np.pi/180,threshold=max(8,int(length*.3)),minLineLength=max(8,int(length*.6)),maxLineGap=max(3,int(length*.06)))
    if lines is None: return False
    positions=[]
    for x,y,X,Y in lines[:,0,:]:
        dx,dy=abs(int(X)-int(x)),abs(int(Y)-int(y))
        if (horizontal and dx >= length*.6 and dy <= max(2,dx*.03)):
            positions.append((int(y)+int(Y))/2+y0)
        elif (not horizontal and dy >= length*.6 and dx <= max(2,dy*.03)):
            positions.append((int(x)+int(X))/2+x0)
    minimum=max(3,thickness*.15)
    return any(minimum <= abs(a-b) <= thickness*1.5 for i,a in enumerate(positions) for b in positions[i+1:])


def exterior_window_symbols(edges, walls, bounds):
    """Propose paired exterior strokes anchored at both ends to wall candidates."""
    if bounds is None or not walls: return []
    shortest=min(edges.shape)
    raw=cv2.HoughLinesP(edges,1,np.pi/180,threshold=max(8,int(shortest*.025)),minLineLength=max(10,int(shortest*.05)),maxLineGap=8)
    if raw is None: return []
    lines=[]
    for x,y,X,Y in raw[:,0,:]:
        dx,dy=abs(int(X)-int(x)),abs(int(Y)-int(y)); horizontal=dx>dy
        if min(dx,dy)>max(2,max(dx,dy)*.02): continue
        axis=(int(y)+int(Y))/2 if horizontal else (int(x)+int(X))/2
        lo,hi=sorted((int(x),int(X))) if horizontal else sorted((int(y),int(Y)))
        midpoint=Point((lo+hi)/2,axis) if horizontal else Point(axis,(lo+hi)/2)
        if bounds.distance(midpoint)<=shortest*.045: lines.append((horizontal,axis,lo,hi))
    pairs=[]
    wall_geometry=[(w,LineString([w['start'],w['end']])) for w in walls]
    for i,a in enumerate(lines):
        for b in lines[i+1:]:
            if a[0]!=b[0] or not max(3,shortest*.004)<=abs(a[1]-b[1])<=shortest*.035: continue
            lo,hi=max(a[2],b[2]),min(a[3],b[3]); overlap=hi-lo
            if overlap/max(a[3]-a[2],b[3]-b[2])<.7: continue
            axis=(a[1]+b[1])/2
            start,end=([lo,axis],[hi,axis]) if a[0] else ([axis,lo],[axis,hi])
            candidate=LineString([start,end])
            if any(candidate.intersection(geom.buffer(max(w['thickness']*.6,shortest*.012))).length/candidate.length>.5 for w,geom in wall_geometry): continue
            nearest=[]
            for point in (start,end):
                distance,wall_id=min((math.dist(point,p),w['id']) for w in walls for p in (w['start'],w['end']))
                if distance>shortest*.025: break
                nearest.append(wall_id)
            if len(nearest)!=2 or nearest[0]==nearest[1]: continue
            pairs.append({'horizontal':a[0],'axis':axis,'lo':lo,'hi':hi,'wallIds':nearest})
    groups=[]
    for pair in sorted(pairs,key=lambda p:(p['horizontal'],p['axis'],p['lo'])):
        for group in groups:
            sample=group[0]; overlap=min(pair['hi'],sample['hi'])-max(pair['lo'],sample['lo'])
            if pair['horizontal']==sample['horizontal'] and abs(pair['axis']-sample['axis'])<=shortest*.035 and overlap>=.7*max(pair['hi']-pair['lo'],sample['hi']-sample['lo']):
                group.append(pair); break
        else: groups.append([pair])
    result=[]
    for group in groups:
        axis=float(np.median([p['axis'] for p in group]));lo=float(np.median([p['lo'] for p in group]));hi=float(np.median([p['hi'] for p in group]))
        start,end=([lo,axis],[hi,axis]) if group[0]['horizontal'] else ([axis,lo],[axis,hi])
        result.append({'start':start,'end':end,'kind':'window','evidence':'parallel exterior symbol','wallIds':group[0]['wallIds'],'reviewRequired':True})
    return result


def detect(data, image):
    if data.get('kind') != 'normalized-wall-candidates' or data.get('units') != 'px':
        raise ValueError('Expected normalized pixel wall candidates')
    if image is None or image.shape[:2] != (data['image']['height'], data['image']['width']):
        raise ValueError('Image is unreadable or dimensions differ')
    walls=data['walls']; size=min(image.shape[:2]); low=size*.025; high=size*.18
    hull=MultiPoint([p for w in walls for p in (w['start'],w['end'])]).convex_hull
    bounds=hull.boundary if hull.geom_type in ('Polygon', 'LineString') else None
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY); edges=cv2.Canny(gray,60,150)
    candidates=[]
    for i,a in enumerate(walls):
        for b in walls[i+1:]:
            ah=a['start'][1]==a['end'][1]; bh=b['start'][1]==b['end'][1]
            if ah!=bh: continue
            along=0 if ah else 1; axis=1-along
            if abs(a['start'][axis]-b['start'][axis])>max(a['thickness'],b['thickness'])/2: continue
            first,second=sorted((a,b),key=lambda w:min(w['start'][along],w['end'][along]))
            left=max(first['start'][along],first['end'][along]); right=min(second['start'][along],second['end'][along]); width=right-left
            if not low<=width<=size*.34: continue
            wide=width>high
            center=(a['start'][axis]+b['start'][axis])/2
            # Reject a gap crossed or occupied by another aligned candidate.
            if any(c is not a and c is not b and (c['start'][1]==c['end'][1])==ah and abs(c['start'][axis]-center)<=max(c['thickness'],a['thickness'],b['thickness'])/2 and min(c['start'][along],c['end'][along])<right and max(c['start'][along],c['end'][along])>left for c in walls): continue
            start=[left,center] if ah else [center,left]; end=[right,center] if ah else [center,right]
            mx,my=(start[0]+end[0])/2,(start[1]+end[1])/2
            radius=int(width); x0=max(0,int(mx-radius)); x1=min(image.shape[1],int(mx+radius)); y0=max(0,int(my-radius)); y1=min(image.shape[0],int(my+radius))
            lines=cv2.HoughLinesP(edges[y0:y1,x0:x1],1,np.pi/180,threshold=max(10,int(width*.25)),minLineLength=max(10,int(width*.35)),maxLineGap=4)
            diagonal=False
            if lines is not None:
                for line in lines[:,0,:]:
                    x,y,X,Y=map(int,line); dx=abs(X-x);dy=abs(Y-y)
                    if min(dx,dy)>max(dx,dy)*.25:
                        # Door leaves should be near one of the gap endpoints.
                        points=((x+x0,y+y0),(X+x0,Y+y0))
                        if min(math.dist(p,q) for p in points for q in (start,end)) < width*.35:
                            diagonal=True; break
            exterior=bounds is not None and bounds.distance(Point(mx,my)) <= max(a['thickness'],b['thickness'])*1.5
            parallel=not diagonal and (wide or not exterior) and has_parallel_window_lines(edges,start,end,max(a['thickness'],b['thickness']))
            if wide and not parallel: continue
            kind='door' if diagonal else 'window' if exterior or parallel else 'unknown'
            evidence='diagonal line near jamb' if diagonal else 'near convex hull' if exterior else 'parallel lines in opening' if parallel else 'unclassified gap'
            candidates.append({'id':f'o{len(candidates)+1:03}', 'start':start,'end':end,'kind':kind,'evidence':evidence, 'wallIds':[first['id'],second['id']], 'reviewRequired':True})
    for symbol in exterior_window_symbols(edges,walls,bounds):
        line=LineString([symbol['start'],symbol['end']])
        duplicate=False
        for existing in candidates:
            other=LineString([existing['start'],existing['end']])
            if line.intersection(other.buffer(size*.035)).length >= .7*min(line.length,other.length):
                duplicate=True
                if existing['kind']=='unknown': existing.update(kind='window',evidence='parallel exterior symbol')
                break
        if not duplicate:
            symbol['id']=f'o{len(candidates)+1:03}'
            candidates.append(symbol)
    return {'version':'1.0','kind':'opening-candidates','units':'px','scale':data['scale'],'image':data['image'],'reviewRequired':True,'openings':candidates,'uncertainties':['Heuristic candidates only; diagonal furniture can resemble a door and convex hull is an approximate exterior.','Openings can be missed where wall fragments are missing or misaligned; window/door type requires review.']}


def run(source,image_path,output):
    source,image_path,output=Path(source),Path(image_path),Path(output)
    if output.exists(): raise FileExistsError(f'Output already exists: {output}')
    data=json.loads(source.read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Invalid number')))
    image=cv2.imread(str(image_path)); result=detect(data,image); overlay=image.copy()
    colors={'door':(40,180,40),'window':(255,110,0),'unknown':(0,80,255)}
    for o in result['openings']:
        a=tuple(round(x) for x in o['start']); b=tuple(round(x) for x in o['end']); color=colors[o['kind']]
        cv2.line(overlay,a,b,color,5); p=(round((a[0]+b[0])/2),round((a[1]+b[1])/2));cv2.putText(overlay,o['id'],p,cv2.FONT_HERSHEY_SIMPLEX,.45,color,2,cv2.LINE_AA)
    ok,buf=cv2.imencode('.png',overlay)
    if not ok: raise ValueError('Cannot encode overlay')
    output.mkdir(parents=True,exist_ok=False)
    try:
        (output/'openings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        (output/'overlay.png').write_bytes(buf.tobytes())
    except BaseException:
        shutil.rmtree(output); raise
    return result
