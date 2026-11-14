# SPDX-License-Identifier: AGPL-3.0-only
"""Independent per-engine SimConnect requests and auditable fuel-flow selection.

Does not infer per-engine FF from FOB or corrected/estimated engine data.
Each engine/index has its *own* Request. The upstream AircraftRequests.get()
shares and redefines a Request when alternately reading :1 and :2, which can
result in missing values or intermittent reads.
"""
import math

KG_PER_LB = 0.45359237


def finite_nonnegative(value):
    try:
        if value is None:
            return None
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError):
        return None


class IniBuildsFuelFlowProbe:
    """Read user-identified iniBuilds LVar candidates without assuming units.

    Both identifiers and their kg/s unit have been checked against cockpit
    fuel-flow indications by the user. The probe remains raw and independent
    of the configured measured-flow adapter to aid diagnostics.
    """
    NAMES = {1: 'L:INI_FUEL_FLOW1', 2: 'L:INI_FUEL_FLOW2'}

    def __init__(self, simconnect, request_factory=None):
        if request_factory is None:
            from SimConnect import Request as request_factory
        self.requests = {
            engine: request_factory((name.encode('ascii'), b'Number'), simconnect, _time=800)
            for engine, name in self.NAMES.items()
        }

    def sample(self):
        result = {}
        for engine, name in self.NAMES.items():
            try:
                raw = finite_nonnegative(self.requests[engine].value)
            except Exception:
                raw = None
            result[f'engine{engine}'] = {
                'name': name,
                'raw': raw,
                'unit': 'kg/s (user-confirmed)',
                'status': 'POSITIVE_RAW_USER_CONFIRMED' if raw is not None and raw > 0
                          else ('ZERO_NOT_PROOF_OF_EXISTENCE' if raw == 0 else 'UNAVAILABLE'),
            }
        return result


class EngineFuelReader:
    """Read-only sampler bound to a single SimConnect session."""

    # Labeled fields remain distinct; corrected flow is not actual fuel flow.
    SPECS = {
        'turb_pph': ('TURB ENG FUEL FLOW PPH', 'Pounds per hour'),
        'eng_pph': ('ENG FUEL FLOW PPH', 'Pounds per hour'),
        'eng_gph': ('ENG FUEL FLOW GPH', 'Gallons per hour'),
        'corrected_pph': ('TURB ENG CORRECTED FF', 'Pounds per hour'),
        'combustion': ('GENERAL ENG COMBUSTION', 'Bool'),
        'n1': ('TURB ENG N1', 'Percent'),
    }

    def __init__(self, simconnect, request_factory=None, aircraft_adapter=None, ini_probe=None):
        if request_factory is None:
            from SimConnect import Request as request_factory
        self.aircraft_adapter = aircraft_adapter
        self.ini_probe = ini_probe
        self.requests = {}
        for engine in (1, 2):
            for name, (simvar, unit) in self.SPECS.items():
                # The index belongs to this immutable Request; there is no
                # repeated setIndex()/ClearDataDefinition() at sampling time.
                self.requests[engine, name] = request_factory(
                    (f'{simvar}:{engine}'.encode('ascii'), unit.encode('ascii')),
                    simconnect, _time=800,
                )

    def _get(self, engine, name):
        try:
            return finite_nonnegative(self.requests[engine, name].value)
        except Exception:
            return None

    @staticmethod
    def choose(raw, combustion=None, n1=None, density_lb_gal=None):
        """Select observed FF only, never impute from FOB slope or N1.

        Prefer TURB PPH, then ENG PPH. GPH is used only when measured fuel
        density is valid. If an engine appears to be running and all signals
        read zero, report missing rather than silently claiming zero burn.
        """
        turb = finite_nonnegative(raw.get('turb_pph'))
        eng = finite_nonnegative(raw.get('eng_pph'))
        gph = finite_nonnegative(raw.get('eng_gph'))
        density = finite_nonnegative(density_lb_gal)
        gph_pph = gph * density if gph is not None and density is not None and density > 0 else None
        measured = [('TURB ENG FUEL FLOW PPH', turb),
                    ('ENG FUEL FLOW PPH', eng),
                    ('ENG FUEL FLOW GPH × FUEL WEIGHT PER GALLON', gph_pph)]
        positives = [(name, value) for name, value in measured if value is not None and value > 0]
        messages = []
        if len(positives) >= 2:
            a, b = positives[:2]
            if abs(a[1] - b[1]) / max(a[1], b[1]) > 0.15:
                messages.append('Standard fuel-flow sources disagree by more than 15%; compare with cockpit.')
        if positives:
            source, pph = positives[0]
            return round(pph * KG_PER_LB, 3), source, 'MEASURED', messages

        if combustion is not None and combustion >= 0.5:
            messages.append('Engine combustion active, but no positive fuel-flow SimVar is available.')
            return None, '', 'MISSING_WHILE_RUNNING', messages
        if combustion is None and n1 is not None and n1 >= 12:
            messages.append('N1 present without combustion confirmation; zero fuel flow is unverified.')
            return None, '', 'UNVERIFIED_ZERO_WITH_N1', messages
        zeros = [(name, value) for name, value in measured if value == 0]
        if zeros:
            return 0.0, zeros[0][0], 'ZERO_REPORTED', messages
        messages.append('No valid fuel-flow SimVar; engine-specific value not estimated.')
        return None, '', 'NO_DATA', messages

    def sample(self, density_lb_gal=None):
        data = {}
        diagnoses = {}
        custom = self.aircraft_adapter.sample() if self.aircraft_adapter else {}
        ini_results = self.ini_probe.sample() if self.ini_probe else {}
        for engine in (1, 2):
            raw = {key: self._get(engine, key) for key in self.SPECS}
            flow, source, status, notes = self.choose(
                raw, combustion=raw['combustion'], n1=raw['n1'], density_lb_gal=density_lb_gal,
            )
            custom_entry = custom.get(f'engine{engine}') or {}
            ini_probe_entry = ini_results.get(f'engine{engine}') or {}
            if ini_probe_entry.get('status') == 'POSITIVE_RAW_USER_CONFIRMED' and custom_entry.get('name') != ini_probe_entry.get('name'):
                notes.append('iniBuilds raw fuel-flow is available, but the measured-flow adapter is not configured for this variable. Confirm profile settings and cockpit.')
            custom_flow=custom_entry.get('ff_kg_h')
            if custom_flow is not None:
                if flow is not None and flow > 0 and abs(flow-custom_flow)/max(flow,custom_flow) > .15:
                    notes.append('Configured LVar disagrees with standard SimVar by more than 15%.')
                flow=custom_flow
                source='Custom aircraft variable: '+str(custom_entry.get('name'))
                status=custom_entry.get('state','DIRECT_LVAR_UNVERIFIED')
                notes.append('Direct LVar reading; units and source must be checked if aircraft version or fuel system changes.')
            elif custom_entry.get('name') and status=='MISSING_WHILE_RUNNING':
                notes.append('Configured LVar did not return a usable positive fuel flow.')
            data[f'ff{engine}_kg_h'] = flow
            data[f'ff{engine}_source'] = source or None
            data[f'engine{engine}_combustion'] = raw['combustion']
            data[f'engine{engine}_n1_pct'] = raw['n1']
            diagnoses[f'engine{engine}'] = {
                'status': status,
                'selected_source': source or None,
                'selected_ff_kg_h': flow,
                'turb_pph': raw['turb_pph'],
                'eng_pph': raw['eng_pph'],
                'eng_gph': raw['eng_gph'],
                'corrected_pph_diagnostic_only':raw['corrected_pph'],
                'fuel_weight_lb_gal': finite_nonnegative(density_lb_gal),
                'combustion': raw['combustion'],
                'n1_pct': raw['n1'],
                'custom':custom_entry,
                'ini_lvar_probe': ini_probe_entry,
                'notes': notes,
            }
        ff1 = data['ff1_kg_h']
        ff2 = data['ff2_kg_h']
        data['ff_total_kg_h'] = round(ff1 + ff2, 3) if ff1 is not None and ff2 is not None else None
        data['ff_diagnostics'] = diagnoses
        return data
