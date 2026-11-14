# SPDX-License-Identifier: AGPL-3.0-only
"""Read iniBuilds A350 per-engine anti-ice switch state without controlling the aircraft.

Manufacturer-documented A350 variables (iniBuilds February 2025 key LVar list):
  L:INI_ENG_ANTI_ICE1_STATE, L:INI_ENG_ANTI_ICE2_STATE
Microsoft MSFS 2024 SimVars checked for corroboration:
  ENG ANTI ICE:1/2 and GENERAL ENG ANTI ICE POSITION:1/2.
A returned value is a switch/system-state indication, not proof of pneumatic flow.
"""
import math


class EngineAntiIceReader:
    SPECS = {
        'inibuilds_lvar': ('L:INI_ENG_ANTI_ICE{engine}_STATE', 'Number'),
        'eng_anti_ice': ('ENG ANTI ICE:{engine}', 'Bool'),
        'general_position': ('GENERAL ENG ANTI ICE POSITION:{engine}', 'Bool'),
    }

    def __init__(self, simconnect, request_factory=None):
        if request_factory is None:
            from SimConnect import Request as request_factory
        self.requests = {}
        for engine in (1, 2):
            for key, (template, unit) in self.SPECS.items():
                name = template.format(engine=engine)
                self.requests[engine, key] = request_factory(
                    (name.encode('ascii'), unit.encode('ascii')), simconnect, _time=800,
                )

    def _get(self, engine, key):
        try:
            v = self.requests[engine, key].value
            if v is None:
                return None
            v = float(v)
            if not math.isfinite(v) or v not in (0., 1.):
                return None
            return int(v)
        except Exception:
            return None

    def sample(self, is_inibuilds_a350=False):
        result = {}
        diagnostics = {}
        for engine in (1, 2):
            readings = {key: self._get(engine, key) for key in self.SPECS}
            preferred = (
                ('inibuilds_lvar', 'L:INI_ENG_ANTI_ICE%d_STATE' % engine),
                ('eng_anti_ice', 'ENG ANTI ICE:%d' % engine),
                ('general_position', 'GENERAL ENG ANTI ICE POSITION:%d' % engine),
            ) if is_inibuilds_a350 else (
                ('eng_anti_ice', 'ENG ANTI ICE:%d' % engine),
                ('general_position', 'GENERAL ENG ANTI ICE POSITION:%d' % engine),
            )
            selected = next(((key, label, readings[key]) for key, label in preferred
                             if readings[key] is not None), None)
            state = selected[2] if selected else None
            source = selected[1] if selected else None
            disagree = bool(selected and any(
                readings[key] is not None and readings[key] != state
                for key, _ in preferred if key != selected[0]
            ))
            status = 'CONFLICT_CHECK_COCKPIT' if disagree else ('REPORTED_SWITCH_STATE' if selected else 'UNAVAILABLE')
            result[f'engine{engine}_antiice'] = state
            result[f'engine{engine}_antiice_source'] = source
            diagnostics[f'engine{engine}'] = {
                'state':state, 'label':('ON' if state == 1 else 'OFF' if state == 0 else 'N/A'),
                'source':source, 'status':status, 'raw':readings,
                'notes':('Variables disagree; validate against overhead panel.' if disagree else
                         'Switch state; actual pneumatic ice-protection performance is not inferred.'),
            }
        result['antiice_diagnostics'] = diagnostics
        return result
