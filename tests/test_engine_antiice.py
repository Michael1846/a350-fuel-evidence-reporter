# SPDX-License-Identifier: AGPL-3.0-only
import csv
import tempfile
import unittest
from pathlib import Path
from engine_antiice_reader import EngineAntiIceReader
from telemetry_store import TelemetryStore
from evidence_capture import freeze_sim_context

class FakeRequest:
    values={}
    instances=[]
    def __init__(self, ident, simconnect, _time=800):
        self.key=ident[0].decode('ascii')
        self.instances.append(self.key)
    @property
    def value(self):
        return self.values.get(self.key)

class EngineAntiIceTests(unittest.TestCase):
    def setUp(self):
        FakeRequest.values={}
        FakeRequest.instances=[]

    def test_pinned_requests_for_two_engines(self):
        reader=EngineAntiIceReader(object(),FakeRequest)
        self.assertEqual(len(FakeRequest.instances),6)
        self.assertIn('L:INI_ENG_ANTI_ICE1_STATE', FakeRequest.instances)
        self.assertIn('L:INI_ENG_ANTI_ICE2_STATE', FakeRequest.instances)
        self.assertEqual(FakeRequest.instances.count('ENG ANTI ICE:2'),1)

    def test_documented_lvars_are_preferred_even_when_off(self):
        FakeRequest.values={
            'L:INI_ENG_ANTI_ICE1_STATE':0,
            'L:INI_ENG_ANTI_ICE2_STATE':1,
            'ENG ANTI ICE:1':0,
            'ENG ANTI ICE:2':1,
            'GENERAL ENG ANTI ICE POSITION:1':0,
            'GENERAL ENG ANTI ICE POSITION:2':1,
        }
        result=EngineAntiIceReader(object(),FakeRequest).sample(is_inibuilds_a350=True)
        self.assertEqual([result['engine1_antiice'],result['engine2_antiice']],[0,1])
        self.assertEqual(result['antiice_diagnostics']['engine1']['label'],'OFF')
        self.assertEqual(result['antiice_diagnostics']['engine2']['label'],'ON')
        self.assertEqual(result['engine1_antiice_source'],'L:INI_ENG_ANTI_ICE1_STATE')

    def test_conflict_is_visible(self):
        FakeRequest.values={'L:INI_ENG_ANTI_ICE1_STATE':0,'ENG ANTI ICE:1':1}
        data=EngineAntiIceReader(object(),FakeRequest).sample(is_inibuilds_a350=True)
        self.assertEqual(data['engine1_antiice'],0)
        self.assertEqual(data['antiice_diagnostics']['engine1']['status'],'CONFLICT_CHECK_COCKPIT')

    def test_non_a350_ignores_inibuilds_lvar(self):
        FakeRequest.values={'L:INI_ENG_ANTI_ICE1_STATE':1,'ENG ANTI ICE:1':0}
        data=EngineAntiIceReader(object(),FakeRequest).sample(is_inibuilds_a350=False)
        self.assertEqual(data['engine1_antiice'],0)
        self.assertEqual(data['engine1_antiice_source'],'ENG ANTI ICE:1')
        self.assertEqual(data['engine2_antiice'],None)

    def test_unknown_does_not_become_off(self):
        data=EngineAntiIceReader(object(),FakeRequest).sample(is_inibuilds_a350=True)
        self.assertIsNone(data['engine1_antiice'])
        self.assertEqual(data['antiice_diagnostics']['engine2']['label'],'N/A')

    def test_csv_preserves_both_states_and_sources_and_migrates(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'t.csv'
            with path.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=['timestamp_unix','fob_kg','engine1_antiice','engine2_antiice']);w.writeheader()
                w.writerow({'timestamp_unix':123,'fob_kg':8300,'engine1_antiice':1,'engine2_antiice':0})
            store=TelemetryStore(path)
            store.append({'fob_kg':8290,'lat':48,'engine1_antiice':0,'engine2_antiice':1,
                          'engine1_antiice_source':'L:INI_ENG_ANTI_ICE1_STATE',
                          'engine2_antiice_source':'L:INI_ENG_ANTI_ICE2_STATE'},1700000000)
            rows=store.recent()
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['engine1_antiice'],'1')
            self.assertEqual(rows[1]['engine1_antiice'],'0')
            self.assertEqual(rows[1]['engine2_antiice'],'1')
            self.assertEqual(rows[1]['engine1_antiice_source'],'L:INI_ENG_ANTI_ICE1_STATE')

    def test_evidence_freezes_antiice_context(self):
        status={'state':'connected','timestamp':1700000000,'identity':{'title':'A350'},
                'data':{'lat':48,'lon':10,'engine1_antiice':1,'engine2_antiice':0,
                        'engine1_antiice_source':'L:INI_ENG_ANTI_ICE1_STATE'}}
        snap=freeze_sim_context(status,trigger_time=1700000001)
        self.assertEqual([snap['engine1_antiice'],snap['engine2_antiice']],[1,0])
        self.assertEqual(snap['engine1_antiice_source'],'L:INI_ENG_ANTI_ICE1_STATE')

if __name__=='__main__':unittest.main()
