# SPDX-License-Identifier: AGPL-3.0-only
import json
import tempfile
import unittest
from pathlib import Path
from aircraft_engine_adapter import AircraftEngineAdapter,load_profile,normalize_profile,save_profile
from engine_fuel_reader import EngineFuelReader,IniBuildsFuelFlowProbe,KG_PER_LB
from lvar_source_scan import scan
from telemetry_store import TelemetryStore
from app import telemetry_trend_png
from PIL import Image
import io
import csv

class Request:
    values={}
    def __init__(self,ident,sim,_time=800):
        self.ident=ident[0].decode('ascii')
    @property
    def value(self):return self.values.get(self.ident)

class DirectAdapterTests(unittest.TestCase):
    def test_user_validated_a350_default(self):
        with tempfile.TemporaryDirectory() as td:
            profile=load_profile(Path(td)/'none.json')
            self.assertEqual(profile['engine1'], {'name':'L:INI_FUEL_FLOW1','unit':'kg/s'})
            self.assertEqual(profile['engine2'], {'name':'L:INI_FUEL_FLOW2','unit':'kg/s'})
    def test_prevent_invalid_names_and_units(self):
        for var in ('L:GOOD;DELETE','A:TURB ENG N1:1','L:','L:x\nother'):
            with self.assertRaises(ValueError):normalize_profile({'engine1':{'name':var}})
        with self.assertRaises(ValueError):normalize_profile({'engine1':{'name':'L:ENGINEFF','unit':'Celsius'}})
    def test_direct_read_both_separately_and_convert(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'cfg.json'
            save_profile(path,{'engine1':{'name':'L:ENG1_FF','unit':'lb/h'},'engine2':{'name':'L:ENG2_FF','unit':'kg/min'}})
            Request.values={'L:ENG1_FF':10000,'L:ENG2_FF':80}
            reader=AircraftEngineAdapter(object(),path,Request)
            data=reader.sample()
            self.assertAlmostEqual(data['engine1']['ff_kg_h'],10000*KG_PER_LB,places=3)
            self.assertEqual(data['engine2']['ff_kg_h'],4800)
            self.assertEqual(data['engine1']['state'],'DIRECT_LVAR_UNVERIFIED')
            self.assertEqual(reader.sample()['engine2']['ff_kg_h'],4800)
            save_profile(path,{'engine1':{'name':'L:ENG1_FF','unit':'lb/h'},'engine2':{'name':'','unit':'kg/h'}})
            self.assertEqual(reader.sample()['engine2']['state'],'NOT_CONFIGURED')
    def test_inibuilds_default_kg_s_to_kg_h_and_both_engines(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/'engine_sources.json'  # not yet created
            Request.values={'L:INI_FUEL_FLOW1':0.22790074348449707,
                            'L:INI_FUEL_FLOW2':0.2694722222,
                            'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
                            'TURB ENG N1:1':21.3,'TURB ENG N1:2':23.3,
                            'TURB ENG FUEL FLOW PPH:1':0,'TURB ENG FUEL FLOW PPH:2':0,
                            'ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:2':0,
                            'ENG FUEL FLOW GPH:1':0,'ENG FUEL FLOW GPH:2':0}
            adapter=AircraftEngineAdapter(object(),cfg,Request)
            data=EngineFuelReader(object(),Request,adapter).sample()
            self.assertAlmostEqual(data['ff1_kg_h'],820.443,places=3)
            self.assertAlmostEqual(data['ff2_kg_h'],970.1,places=1)
            self.assertAlmostEqual(data['ff_total_kg_h'],1790.543,places=2)
            self.assertEqual(data['ff_diagnostics']['engine1']['custom']['unit'],'kg/s')
            self.assertEqual(data['ff_diagnostics']['engine1']['status'],'DIRECT_INIBUILDS_FF_USER_CONFIRMED')
            self.assertFalse(cfg.exists()) # never writes config unless explicitly saved

    def test_existing_custom_profile_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/'engine_sources.json'
            profile={'engine1':{'name':'L:OTHER_ENGINE1','unit':'lb/h'},
                     'engine2':{'name':'L:OTHER_ENGINE2','unit':'kg/min'}}
            save_profile(cfg,profile)
            raw=cfg.read_bytes()
            self.assertEqual(load_profile(cfg),profile)
            self.assertEqual(cfg.read_bytes(),raw)

    def test_zero_is_not_claimed_as_actual_flow(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'cfg.json'
            save_profile(path,{'engine1':{'name':'L:ENG1_FF','unit':'kg/h'}})
            Request.values={'L:ENG1_FF':0}
            sample=AircraftEngineAdapter(object(),path,Request).sample()
            self.assertIsNone(sample['engine1']['ff_kg_h'])
            self.assertEqual(sample['engine1']['state'],'ZERO_FROM_LVAR_UNVERIFIED')
    def test_fuel_reader_uses_direct_lvars_when_standard_sources_zero(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'cfg.json'
            save_profile(path,{'engine1':{'name':'L:ENG1_FF','unit':'kg/h'},'engine2':{'name':'L:ENG2_FF','unit':'kg/h'}})
            Request.values={'L:ENG1_FF':3400,'L:ENG2_FF':3500,
                            'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
                            'TURB ENG N1:1':85.35,'TURB ENG N1:2':85.36,
                            'TURB ENG FUEL FLOW PPH:1':0,'TURB ENG FUEL FLOW PPH:2':0,
                            'ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:2':0,
                            'ENG FUEL FLOW GPH:1':0,'ENG FUEL FLOW GPH:2':0}
            adapter=AircraftEngineAdapter(object(),path,Request)
            sampled=EngineFuelReader(object(),Request,adapter).sample()
            self.assertEqual([sampled[k] for k in ('ff1_kg_h','ff2_kg_h','ff_total_kg_h')],[3400,3500,6900])
            self.assertAlmostEqual(sampled['engine1_n1_pct'],85.35)
            self.assertEqual(sampled['ff_diagnostics']['engine1']['status'],'DIRECT_LVAR_UNVERIFIED')
    def test_n1_is_written_into_5s_csv_and_pdf_profile(self):
        with tempfile.TemporaryDirectory() as td:
            store=TelemetryStore(Path(td)/'telemetry.csv')
            for i in range(5):
                store.append({'fob_kg':8000-i*5,'ff1_kg_h':3000,'ff2_kg_h':3100,
                              'engine1_n1_pct':80+i,'engine2_n1_pct':81+i,
                              'ff1_source':'Custom aircraft variable: L:ENG1_FF',
                              'ff2_source':'Custom aircraft variable: L:ENG2_FF',
                              'altitude_ft':33000,'lat':48.0,'lon':9.0},1700000000+i*5)
            lines=store.recent()
            self.assertEqual(lines[-1]['engine1_n1_pct'],'84.0')
            self.assertEqual(lines[-1]['engine2_n1_pct'],'85.0')
            self.assertIn('L:ENG1_FF',lines[-1]['engine1_ff_source'])
            png=telemetry_trend_png(lines)
            self.assertTrue(png.startswith(b'\x89PNG'))
            im=Image.open(io.BytesIO(png))
            self.assertGreater(im.height,900)

    def test_inibuilds_named_lvar_probe_shows_unverified_raw_per_engine(self):
        Request.values={'L:INI_FUEL_FLOW1':1234.5,'L:INI_FUEL_FLOW2':2345.6}
        probe=IniBuildsFuelFlowProbe(object(),Request)
        readings=probe.sample()
        self.assertEqual(readings['engine1']['name'],'L:INI_FUEL_FLOW1')
        self.assertEqual(readings['engine2']['name'],'L:INI_FUEL_FLOW2')
        self.assertEqual(readings['engine1']['raw'],1234.5)
        self.assertEqual(readings['engine2']['raw'],2345.6)
        self.assertEqual(readings['engine1']['unit'],'kg/s (user-confirmed)')
        self.assertEqual(readings['engine2']['status'],'POSITIVE_RAW_USER_CONFIRMED')

    def test_probe_does_not_fake_kg_hour_or_assume_engine2_exists(self):
        Request.values={'L:INI_FUEL_FLOW1':2750,'L:INI_FUEL_FLOW2':0,
            'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
            'TURB ENG N1:1':84,'TURB ENG N1:2':84,
            'TURB ENG FUEL FLOW PPH:1':0,'TURB ENG FUEL FLOW PPH:2':0,
            'ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:2':0,
            'ENG FUEL FLOW GPH:1':0,'ENG FUEL FLOW GPH:2':0}
        probe=IniBuildsFuelFlowProbe(object(),Request)
        result=EngineFuelReader(object(),Request,ini_probe=probe).sample()
        self.assertIsNone(result['ff1_kg_h'])
        self.assertIsNone(result['ff2_kg_h'])
        self.assertIsNone(result['ff_total_kg_h'])
        self.assertEqual(result['ff_diagnostics']['engine1']['ini_lvar_probe']['raw'],2750)
        self.assertEqual(result['ff_diagnostics']['engine2']['ini_lvar_probe']['status'],'ZERO_NOT_PROOF_OF_EXISTENCE')
        self.assertIn('adapter', ' '.join(result['ff_diagnostics']['engine1']['notes']).lower())

    def test_known_probe_names_used_only_after_unit_selected_in_profile(self):
        with tempfile.TemporaryDirectory() as td:
            config=Path(td)/'engine_sources.json'
            save_profile(config,{'engine1':{'name':'L:INI_FUEL_FLOW1','unit':'lb/h'},
                                 'engine2':{'name':'L:INI_FUEL_FLOW2','unit':'lb/h'}})
            Request.values={'L:INI_FUEL_FLOW1':2700,'L:INI_FUEL_FLOW2':2800,
                'GENERAL ENG COMBUSTION:1':1,'GENERAL ENG COMBUSTION:2':1,
                'TURB ENG N1:1':85,'TURB ENG N1:2':85,
                'TURB ENG FUEL FLOW PPH:1':0,'TURB ENG FUEL FLOW PPH:2':0,
                'ENG FUEL FLOW PPH:1':0,'ENG FUEL FLOW PPH:2':0,
                'ENG FUEL FLOW GPH:1':0,'ENG FUEL FLOW GPH:2':0}
            adapter=AircraftEngineAdapter(object(),config,Request)
            probe=IniBuildsFuelFlowProbe(object(),Request)
            out=EngineFuelReader(object(),Request,aircraft_adapter=adapter,ini_probe=probe).sample()
            self.assertAlmostEqual(out['ff1_kg_h'],2700*KG_PER_LB,places=3)
            self.assertAlmostEqual(out['ff2_kg_h'],2800*KG_PER_LB,places=3)
            self.assertAlmostEqual(out['ff_total_kg_h'],5500*KG_PER_LB,places=3)
            self.assertEqual(out['ff_diagnostics']['engine1']['selected_source'],'Custom aircraft variable: L:INI_FUEL_FLOW1')

    def test_old_telemetry_csv_header_is_upgraded_without_data_loss(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'telemetry.csv'
            old_headers=['timestamp_unix','timestamp_utc','fob_kg','engine1_ff_kg_h','engine2_ff_kg_h']
            with path.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=old_headers)
                writer.writeheader()
                writer.writerow({'timestamp_unix':'1700000000','timestamp_utc':'2023-11-14 UTC',
                                 'fob_kg':'8000','engine1_ff_kg_h':'3200','engine2_ff_kg_h':'3300'})
            store=TelemetryStore(path)
            self.assertEqual(store.count,1)
            self.assertEqual(store.recent()[0]['fob_kg'],'8000')
            store.append({'fob_kg':7990,'ff1_kg_h':3300,'ff2_kg_h':3300,
                          'ff1_source':'Direct variable A', 'lat':48},1700000005)
            data=store.recent()
            self.assertEqual(len(data),2)
            self.assertEqual(data[0]['engine1_ff_source'],'')
            self.assertEqual(data[1]['engine1_ff_source'],'Direct variable A')

    def test_scan_candidates_without_changing_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            content='<Script>(L:INI_ENG1_FUEL_FLOW, number) (L:INI_ENG2_FF, number)</Script>'
            doc=root/'gauge.xml';doc.write_text(content)
            before=doc.read_text()
            result=scan(root)
            names=[i['name'] for i in result['candidates']]
            self.assertIn('L:INI_ENG1_FUEL_FLOW',names)
            self.assertIn('L:INI_ENG2_FF',names)
            self.assertEqual(before,doc.read_text())

if __name__=='__main__':unittest.main()
