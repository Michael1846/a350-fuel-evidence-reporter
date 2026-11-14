# SPDX-License-Identifier: AGPL-3.0-only
import json, tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aircraft_identity import detect_variant,package_version,as_text
from telemetry_store import TelemetryStore
from simbridge import Bridge
import threading

class AircraftIdentityTests(unittest.TestCase):
    def test_variant_classification_conservative(self):
        self.assertEqual(detect_variant('iniBuilds Airbus A350-900 No Cabin')['variant'],'A350-900')
        self.assertEqual(detect_variant('A350-900 ULR')['variant'],'A350-900 ULR')
        self.assertEqual(detect_variant('A350-1000 with cabin')['variant'],'A350-1000')
        self.assertEqual(detect_variant('iniBuilds Airbus A350')['variant'],'')
        self.assertEqual(detect_variant('Boeing 777')['family'],'')
        self.assertEqual(as_text(b'Airbus A350-900\x00padding'),'Airbus A350-900')

    def test_manifest_version_and_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            target=root/'inibuilds-aircraft-a350'
            target.mkdir()
            (target/'manifest.json').write_text(json.dumps({'package_version':'1.2.8'}))
            repaint=root/'inibuilds-aircraft-a350-livery'
            repaint.mkdir()
            (repaint/'manifest.json').write_text(json.dumps({'package_version':'3.0.1'}))
            p=package_version('A350',[root])
            self.assertEqual(p['version'],'1.2.8')
            self.assertEqual(p['status'],'manifest_candidate')
            other=root/'inibuilds-a350-extra'
            other.mkdir();(other/'manifest.json').write_text(json.dumps({'package_version':'1.2.7'}))
            self.assertEqual(package_version('A350',[root])['status'],'ambiguous')

    def test_identity_updates_state_without_claiming_unavailable_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            state={'tracking_enabled':True,'meta':{'version':'','variant':'','cabin':'','sim':'MSFS 2024'}}
            b=Bridge(lambda:json.loads(json.dumps(state)),lambda v:state.update(v),threading.RLock())
            class Fake:
                def get(self,key):return {'TITLE':'iniBuilds A350-900 No Cabin','ATC_MODEL':'A359','ATC_TYPE':'A359'}.get(key)
            with patch('simbridge.package_version',return_value={'version':'','status':'not_found','candidates':[]}),patch('simbridge.simulator_process',return_value=''):
                b._capture_identity(Fake())
            self.assertEqual(state['meta']['variant'],'A350-900')
            self.assertEqual(state['meta']['cabin'],'No Cabin')
            self.assertEqual(state['meta']['version'],'')
            self.assertEqual(b._identity['version_status'],'not_found')
            b._update_flight_status({'on_ground':1})
            self.assertEqual(b._flight_status,'GROUND')
            b._update_flight_status({'on_ground':0})
            self.assertEqual(b._flight_status,'AIRBORNE')
            b._update_flight_status({'on_ground':1})
            self.assertEqual(b._flight_status,'LANDED')

    def test_profile_samples_preserve_ff_peak(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'series.csv';store=TelemetryStore(p)
            for i in range(3000):
                store.append({'fob_kg':10000-i/20,'ff_total_kg_h':9800 if i==1571 else 4100,
                              'ff1_kg_h':4900 if i==1571 else 2050,
                              'altitude_ft':33000+i/10},i*5+1000)
            reduced=store.profile(600)
            self.assertLessEqual(len(reduced),600)
            self.assertEqual(len(list(store.recent(4000))),3000)
            self.assertTrue(any(float(r['total_ff_kg_h'])==9800 for r in reduced))

if __name__=='__main__':unittest.main()
