# SPDX-License-Identifier: AGPL-3.0-only
"""Evidence groups are ordered user-authored cases. Screenshots retain own metadata.

All requirements are advisory; exports never depend on completeness.
"""
from datetime import datetime, timezone
import secrets

VALID_ISSUES = {'ground_efob','enroute_efob','excessive_burn','other'}

def new_group(title, issue_type, remark=''):
    if issue_type not in VALID_ISSUES: raise ValueError('Unknown issue type')
    return {'id':secrets.token_hex(8),'title':str(title or '').strip()[:120] or 'Untitled observation',
            'issue_type':issue_type,'remark':str(remark or '')[:4000],
            'created_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'), 'screenshot_ids':[]}

def get_group(state, group_id):
    return next((g for g in state.get('groups',[]) if g.get('id')==group_id),None)

def ensure_group(state, group_id):
    if group_id and not get_group(state,group_id): raise ValueError('Unknown event group')
    return group_id or ''

def assign_screenshot(state,screenshot_id,group_id):
    group_id=ensure_group(state,group_id)
    shot=next((s for s in state.get('evidence',[]) if s.get('id')==screenshot_id),None)
    if not shot: raise ValueError('Screenshot not found')
    for group in state.get('groups',[]):
        group['screenshot_ids']=[x for x in group.get('screenshot_ids',[]) if x!=screenshot_id]
    shot['group_id']=group_id
    if group_id: get_group(state,group_id)['screenshot_ids'].append(screenshot_id)

def reorder_screenshot(state,group_id,screenshot_id,direction):
    group=get_group(state,group_id)
    if not group: raise ValueError('Unknown group')
    ids=group.setdefault('screenshot_ids',[])
    if screenshot_id not in ids: raise ValueError('Screenshot not in group')
    idx=ids.index(screenshot_id)
    dest=idx+int(direction)
    if int(direction) not in (-1,1): raise ValueError('Invalid move')
    if 0<=dest<len(ids): ids[idx],ids[dest]=ids[dest],ids[idx]

def ordered_screenshots(state,group):
    lookup={x.get('id'):x for x in state.get('evidence',[])}
    return [lookup[x] for x in group.get('screenshot_ids',[]) if x in lookup and lookup[x].get('group_id')==group['id']]

def evidence_audit(state):
    """Checklist per group; absence of files does not block report creation."""
    out=[]
    for group in state.get('groups',[]):
        shots=ordered_screenshots(state,group)
        obs=[o for o in state.get('snapshots',[]) if o.get('group_id')==group['id']]
        saves=[b for b in state.get('autosaves',[]) if b.get('group_id')==group['id']]
        issue=group['issue_type']
        fields=[]
        if issue=='enroute_efob':
            fields=[('fms_value',any(str(o.get('fms_efob_kg','')).strip() for o in obs)),
                    ('fms_screen',any(s.get('purpose')=='fms_fuel_load' for s in shots)),
                    ('engine_ff_screen',any(s.get('purpose')=='engine_ff' for s in shots)),
                    ('ois_autosave',bool(saves))]
        elif issue=='excessive_burn':
            fields=[('fuel_flow_values',any(str(o.get('ff1_kg_h','')).strip() or str(o.get('ff2_kg_h','')).strip() for o in obs)),
                    ('engine_ff_screen',any(s.get('purpose')=='engine_ff' for s in shots)),
                    ('fms_screen',any(s.get('purpose')=='fms_fuel_load' for s in shots)),
                    ('ois_autosave',bool(saves))]
        elif issue=='ground_efob':
            fields=[('fms_value',any(str(o.get('fms_efob_kg','')).strip() for o in obs)),
                    ('fms_screen',any(s.get('purpose') in ('fms_fuel_load','preflight_prediction') for s in shots))]
        return_item={'id':group['id'],'title':group['title'],'issue_type':issue,
                     'count_screenshots':len(shots),'count_autosaves':len(saves),'count_observations':len(obs),
                     'requirements':[{'id':key,'done':val,'status':'available' if val else 'missing'} for key,val in fields],
                     'remaining':sum(not val for _,val in fields), 'export_allowed':True}
        out.append(return_item)
    return out
