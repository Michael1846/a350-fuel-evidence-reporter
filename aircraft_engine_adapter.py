# SPDX-License-Identifier: AGPL-3.0-only
"""Read *named* aircraft-specific engine fuel-flow variables using SimConnect.

The iniBuilds A350 engine flow LVars and kg/s -> kg/h conversion have been
confirmed by the user against the cockpit. This is a user-supplied in-simulator
validation, not a published manufacturer guarantee for all add-on versions.
Read-only requests; a missing or zero value never creates fictitious flow.
"""
import json
import math
import re
from pathlib import Path
from engine_fuel_reader import finite_nonnegative, KG_PER_LB

VALID_NAME = re.compile(r'^(?:L:|L:1:|Z:)[A-Za-z_][A-Za-z0-9_:.\-/]{0,140}$', re.I)
UNITS = {'kg/h': 1.0, 'lb/h': KG_PER_LB, 'kg/min': 60.0, 'lb/min': 60.0 * KG_PER_LB,
         'kg/s': 3600.0, 'lb/s': 3600.0 * KG_PER_LB}
# A350-specific source validated in the user's running aircraft in November 2026.
# Keep explicitly saved profiles unchanged; this is the fresh-install default.
DEFAULT_PROFILE = {
    'engine1': {'name': 'L:INI_FUEL_FLOW1', 'unit': 'kg/s'},
    'engine2': {'name': 'L:INI_FUEL_FLOW2', 'unit': 'kg/s'},
}
EMPTY_PROFILE = {'engine1': {'name': '', 'unit': 'kg/h'}, 'engine2': {'name': '', 'unit': 'kg/h'}}

def normalize_profile(candidate):
    if not isinstance(candidate, dict): raise ValueError('Expected source profile object')
    profile = {}
    for key in ('engine1', 'engine2'):
        source = candidate.get(key) or {}
        if not isinstance(source, dict): raise ValueError('Invalid source for ' + key)
        name = str(source.get('name') or '').strip()
        unit = str(source.get('unit') or 'kg/h').strip().lower()
        if name and not VALID_NAME.fullmatch(name):
            raise ValueError(f'{key}: enter a read-only L:, L:1: or Z: variable name')
        if unit not in UNITS: raise ValueError(f'{key}: unsupported unit')
        profile[key] = {'name': name, 'unit': unit}
    return profile

def load_profile(path):
    try: return normalize_profile(json.loads(Path(path).read_text(encoding='utf-8')))
    except FileNotFoundError: return normalize_profile(DEFAULT_PROFILE)
    except (ValueError, OSError, TypeError): return normalize_profile(EMPTY_PROFILE)

def save_profile(path, body):
    profile = normalize_profile(body)
    p = Path(path);p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    tmp.replace(p)
    return profile

class AircraftEngineAdapter:
    """Session-bound, dynamically reloaded, independent SimConnect LVar reader."""
    def __init__(self, simconnect, profile_path, request_factory=None):
        self.simconnect=simconnect
        self.path=Path(profile_path)
        if request_factory is None:
            from SimConnect import Request as request_factory
        self.factory=request_factory
        self.profile=None
        self.requests={}
        self._fingerprint=None

    def _reload(self):
        profile=load_profile(self.path)
        fingerprint=tuple((k, profile[k]['name'], profile[k]['unit']) for k in ('engine1','engine2'))
        if fingerprint != self._fingerprint:
            # Keep every SimConnect definition separate. Requests are never
            # mutated in-place, which avoids the previous :1/:2 bug.
            old=self.requests
            self.requests={}
            for k in ('engine1','engine2'):
                name=profile[k]['name']
                if name:
                    prev=old.get((k,name))
                    self.requests[k,name]=prev if prev is not None else self.factory(
                        (name.encode('ascii'), b'Number'), self.simconnect, _time=800)
            self.profile=profile
            self._fingerprint=fingerprint

    def sample(self):
        self._reload()
        out={}
        for key in ('engine1','engine2'):
            conf=self.profile[key];name=conf['name']
            entry={'name':name or None,'unit':conf['unit'],'raw':None,'ff_kg_h':None,
                   'state':'NOT_CONFIGURED' if not name else 'NO_VALUE'}
            if name:
                try: raw=finite_nonnegative(self.requests[key,name].value)
                except Exception: raw=None
                entry['raw']=raw
                if raw is not None:
                    flow=raw*UNITS[conf['unit']]
                    # Reject implausible spikes; still only a preliminary
                    # reading until compared with a cockpit indication.
                    if math.isfinite(flow) and 0 < flow <= 30000:
                        entry['ff_kg_h']=round(flow,3)
                        entry['state']=('DIRECT_INIBUILDS_FF_USER_CONFIRMED'
                                        if name in ('L:INI_FUEL_FLOW1','L:INI_FUEL_FLOW2') and conf['unit']=='kg/s'
                                        else 'DIRECT_LVAR_UNVERIFIED')
                    elif raw==0:
                        entry['state']='ZERO_FROM_LVAR_UNVERIFIED'
                    else:entry['state']='OUT_OF_RANGE'
            out[key]=entry
        return out
