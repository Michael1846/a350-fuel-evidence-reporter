# SPDX-License-Identifier: AGPL-3.0-only
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine_fuel_reader import EngineFuelReader, KG_PER_LB
from simbridge import Bridge
from telemetry_store import TelemetryStore


class FakeRequest:
    values = {}
    created = []

    def __init__(self, spec, sm, _time=800):
        self.key = spec[0].decode('ascii')
        FakeRequest.created.append(self.key)

    @property
    def value(self):
        return FakeRequest.values.get(self.key)


class FuelFlowReaderTests(unittest.TestCase):
    def setUp(self):
        FakeRequest.values = {}
        FakeRequest.created = []

    def reader(self):
        return EngineFuelReader(object(), request_factory=FakeRequest)

    def test_per_engine_requests_are_pinned_separately(self):
        sampler=self.reader()
        self.assertEqual(len(FakeRequest.created), 2 * len(EngineFuelReader.SPECS))
        self.assertEqual(len(set(FakeRequest.created)), 2 * len(EngineFuelReader.SPECS))
        FakeRequest.values.update({
            'TURB ENG FUEL FLOW PPH:1': 5700, 'TURB ENG FUEL FLOW PPH:2': 6200,
            'ENG FUEL FLOW PPH:1': 5700, 'ENG FUEL FLOW PPH:2': 6200,
            'GENERAL ENG COMBUSTION:1':1, 'GENERAL ENG COMBUSTION:2':1,
            'TURB ENG N1:1':85, 'TURB ENG N1:2':87,
        })
        for _ in range(3):
            data=sampler.sample()
            self.assertAlmostEqual(data['ff1_kg_h'],5700*KG_PER_LB,2)
            self.assertAlmostEqual(data['ff2_kg_h'],6200*KG_PER_LB,2)
            self.assertAlmostEqual(data['ff_total_kg_h'],11900*KG_PER_LB,2)
            self.assertEqual(data['engine1_combustion'],1)
        self.assertEqual(len(FakeRequest.created), 2 * len(EngineFuelReader.SPECS))

    def test_zero_turb_pph_does_not_mask_valid_eng_pph(self):
        sampler=self.reader()
        FakeRequest.values.update({
            'TURB ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:1':7300,
            'TURB ENG FUEL FLOW PPH:2':0,'ENG FUEL FLOW PPH:2':7200,
            'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
        })
        result=sampler.sample()
        self.assertAlmostEqual(result['ff1_kg_h'],7300*KG_PER_LB,2)
        self.assertAlmostEqual(result['ff2_kg_h'],7200*KG_PER_LB,2)
        self.assertEqual(result['ff_diagnostics']['engine1']['selected_source'],'ENG FUEL FLOW PPH')

    def test_zero_both_sources_with_running_engine_is_missing_not_zero(self):
        sampler=self.reader()
        FakeRequest.values.update({
            'TURB ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:1':0,
            'TURB ENG FUEL FLOW PPH:2':0,'ENG FUEL FLOW PPH:2':0,
            'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
        })
        result=sampler.sample()
        self.assertIsNone(result['ff1_kg_h'])
        self.assertIsNone(result['ff2_kg_h'])
        self.assertIsNone(result['ff_total_kg_h'])
        self.assertEqual(result['ff_diagnostics']['engine1']['status'],'MISSING_WHILE_RUNNING')

    def test_explicit_engine_off_zero_is_valid(self):
        sampler=self.reader()
        FakeRequest.values.update({
            'TURB ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:1':0,
            'GENERAL ENG COMBUSTION:1':0, 'GENERAL ENG COMBUSTION:2':0,
            'TURB ENG FUEL FLOW PPH:2':0, 'ENG FUEL FLOW PPH:2':0,
        })
        result=sampler.sample()
        self.assertEqual(result['ff_total_kg_h'],0)
        self.assertEqual(result['ff_diagnostics']['engine1']['status'],'ZERO_REPORTED')

    def test_gph_fallback_requires_measured_fuel_density(self):
        sampler=self.reader()
        FakeRequest.values.update({
            'TURB ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:1':0,
            'ENG FUEL FLOW GPH:1':1000,'GENERAL ENG COMBUSTION:1':1,
            'ENG FUEL FLOW GPH:2':1050,'GENERAL ENG COMBUSTION:2':1,
        })
        without=sampler.sample()
        self.assertIsNone(without['ff1_kg_h'])
        with_density=sampler.sample(density_lb_gal=6.72)
        self.assertAlmostEqual(with_density['ff1_kg_h'],1000*6.72*KG_PER_LB,2)
        self.assertAlmostEqual(with_density['ff2_kg_h'],1050*6.72*KG_PER_LB,2)
        self.assertIn('GPH',with_density['ff_diagnostics']['engine1']['selected_source'])

    def test_conflicting_positive_sources_warn_without_arbitrary_average(self):
        flow,source,status,notes=EngineFuelReader.choose({'turb_pph':7200,'eng_pph':4000},combustion=1)
        self.assertAlmostEqual(flow,7200*KG_PER_LB,2)
        self.assertEqual(source,'TURB ENG FUEL FLOW PPH')
        self.assertTrue(any('disagree' in note for note in notes))

    def test_missing_values_preserved_in_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=TelemetryStore(Path(tmp)/'telemetry.csv')
            reader=self.reader()
            FakeRequest.values.update({'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
                                       'TURB ENG FUEL FLOW PPH:1':0,'TURB ENG FUEL FLOW PPH:2':0})
            data=reader.sample();data.update({'fob_kg':10000,'lat':48,'lon':9,'on_ground':0,'altitude_ft':33000})
            db.append(data,1000)
            row=db.recent()[0]
            self.assertEqual(row['engine1_ff_kg_h'],'')
            self.assertEqual(row['engine2_ff_kg_h'],'')
            self.assertEqual(row['total_ff_kg_h'],'')

    def test_measured_flows_are_written_to_telemetry_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=TelemetryStore(Path(tmp)/'telemetry.csv')
            sampler=self.reader()
            FakeRequest.values.update({
                'TURB ENG FUEL FLOW PPH:1':5700,'ENG FUEL FLOW PPH:1':0,
                'TURB ENG FUEL FLOW PPH:2':6000,'ENG FUEL FLOW PPH:2':0,
                'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
            })
            data=sampler.sample()
            data.update({'fob_kg':10000,'lat':48.2,'lon':9.3,'on_ground':0,'altitude_ft':35000})
            db.append(data,1000)
            row=db.recent()[0]
            self.assertAlmostEqual(float(row['engine1_ff_kg_h']),5700*KG_PER_LB,1)
            self.assertAlmostEqual(float(row['engine2_ff_kg_h']),6000*KG_PER_LB,1)
            self.assertAlmostEqual(float(row['total_ff_kg_h']),11700*KG_PER_LB,1)

    def test_missing_ff_does_not_turn_running_engine_off(self):
        d={'engine1_combustion':1,'engine2_combustion':1,
           'ff1_kg_h':None,'ff2_kg_h':None}
        self.assertEqual(Bridge.engine_status(d)[0],'RUNNING')

if __name__=='__main__': unittest.main()
