# SPDX-License-Identifier: AGPL-3.0-only
"""Canonical chronological events. Source time and source GPS are never invented."""
from __future__ import annotations
import datetime as dt
import math

UTC=dt.timezone.utc

def parse_time(value):
    if isinstance(value,(float,int)) and math.isfinite(value):return float(value)
    if not value:return None
    text=str(value).strip()
    try:return float(text)
    except (ValueError,TypeError):pass
    try:
        v=dt.datetime.fromisoformat(text.replace(' UTC','+00:00').replace('Z','+00:00'))
        if v.tzinfo is None:v=v.replace(tzinfo=UTC)
        return v.timestamp()
    except ValueError:return None

def coordinate(context):
    if not isinstance(context,dict):return None
    try:
        a=float(context.get('lat'));b=float(context.get('lon'))
        if math.isfinite(a) and math.isfinite(b) and -90<=a<=90 and -180<=b<=180:
            return {'lat':a,'lon':b,'source':context.get('context_source','unknown'),'accuracy_note':context.get('context_status','')}
    except (ValueError,TypeError):pass
    return None

def event_list(state):
    """Return one numbered event per group; ungrouped captures/observations each get one.
    Sort by original evidence UTC not user interface group order. Screenshot order is
    retained inside groups. Avoid using upload-time GPS as original screenshot GPS.
    """
    shots={x['id']:x for x in state.get('evidence',[])}
    snapshots=state.get('snapshots',[])
    grouped=set();listed=[]
    groups=state.get('groups',[])
    for g in groups:
        gid=g['id']
        selected=[shots[i] for i in g.get('screenshot_ids',[]) if i in shots and shots[i].get('group_id')==gid]
        # Legacy v0.6 groups may miss screenshot_ids, retain all linked shots.
        selected += [v for v in shots.values() if v.get('group_id')==gid and v['id'] not in {x['id'] for x in selected}]
        obs=[x for x in snapshots if x.get('group_id')==gid]
        linkedautos=[x for x in state.get('autosaves',[]) if x.get('group_id')==gid]
        grouped.update(x['id'] for x in selected)
        times=[]
        for x in selected:
            t=parse_time(x.get('timestamp'))
            if t is not None:times.append((t,x.get('context')))
        for x in obs:
            t=parse_time(x.get('timestamp'))
            if t is not None:times.append((t,x.get('context') or {'lat':x.get('lat'),'lon':x.get('lon'),'context_source':x.get('context_source')}))
        earliest=min(times,key=lambda x:x[0]) if times else (parse_time(g.get('created_utc')),None)
        # User can choose a specific captured image/observation as the map anchor.
        anchor=next((x for x in selected+obs if x.get('id')==g.get('anchor_capture_id')),None)
        if anchor:
            anchor_coord=coordinate(anchor.get('context') or {'lat':anchor.get('lat'),'lon':anchor.get('lon'),'context_source':'manual_observation'})
        else:
            anchor_coord=next((coordinate(ctx) for _,ctx in sorted(times,key=lambda r:r[0]) if coordinate(ctx)),None)
        listed.append({'raw_id':gid,'kind':'group','title':g.get('title') or 'Observation','category':g.get('issue_type','other'),
                       'remark':g.get('remark',''),'timestamp_unix':earliest[0],'position':anchor_coord,'screenshots':selected,
                       'observations':sorted(obs,key=lambda o:(parse_time(o.get('timestamp')) is None,parse_time(o.get('timestamp')) or float('inf'))),
                       'autosaves':linkedautos,'user_group':g})
    for shot in shots.values():
        if shot['id'] in grouped:continue
        ts=parse_time(shot.get('timestamp'))
        listed.append({'raw_id':shot['id'],'kind':'screenshot','title':shot.get('phase') or 'Screenshot',
                       'category':shot.get('purpose','other'),'remark':shot.get('note',''),'timestamp_unix':ts,
                       'position':coordinate(shot.get('context')),'screenshots':[shot], 'observations':[], 'autosaves':[]})
    for obs in snapshots:
        if any(obs in entry['observations'] for entry in listed):continue
        ts=parse_time(obs.get('timestamp'))
        listed.append({'raw_id':obs.get('id') or ('legacy_fms_'+str(len(listed))),'kind':'observation','title':obs.get('issue_type','FMS observation'),
                       'category':obs.get('issue_type','other'),'remark':obs.get('note',''),'timestamp_unix':ts,
                       'position':coordinate(obs.get('context') or {'lat':obs.get('lat'),'lon':obs.get('lon'),'context_source':obs.get('context_source')}),
                       'screenshots':[],'observations':[obs],'autosaves':[]})
    listed.sort(key=lambda e:(e['timestamp_unix'] is None,e['timestamp_unix'] if e['timestamp_unix'] is not None else float('inf'),e['raw_id']))
    for n,event in enumerate(listed,1):
        event['label']=f'E{n:02d}'
        event['utc']=dt.datetime.fromtimestamp(event['timestamp_unix'],UTC).strftime('%Y-%m-%d %H:%M:%S UTC') if event['timestamp_unix'] is not None else 'Time unknown'
    return listed

def event_summary(events):
    """JSON-safe projection, no duplicate images or proprietary data."""
    return [{k:e.get(k) for k in ('label','raw_id','kind','title','category','remark','utc','timestamp_unix','position')} | {
        'screenshot_count':len(e['screenshots']),'fms_count':len(e['observations']),'autosave_count':len(e['autosaves'])} for e in events]
