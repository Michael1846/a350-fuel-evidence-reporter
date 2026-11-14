# SPDX-License-Identifier: AGPL-3.0-only
import io,sys,json,tempfile,unittest
from pathlib import Path
from PIL import Image
import fitz
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from event_timeline import event_list,event_summary
from route_map import geometry,render_map,track_from_rows
from report_v07 import make_report
from telemetry_store import TelemetryStore
from evidence_groups import evidence_audit
from evidence_checklist import checklist,ISSUE_TYPES
from app import graph_pil,telemetry_trend_png

class V07Tests(unittest.TestCase):
 def make_state(self,folder):
  state={'meta':{'date':'2026-11-07','flight':'LH2304','dep':'EDDS','arr':'EDDV','sim':'MSFS 2024','variant':'A350-900','cabin':'No Cabin','version':'1.2.8','fuel_bias_pct':'11'},
   'route_fixes':[{'ident':'EDDS','lat':48.69,'lon':9.22},{'ident':'MASEK','lat':50.72,'lon':9.60},{'ident':'EDD V','lat':52.46,'lon':9.68}],
   'groups':[{'id':'g1','title':'EFOB transition','issue_type':'enroute_efob','remark':'Before / after EFOB drop','created_utc':'2026-11-07T17:12:00+00:00','screenshot_ids':['a','b','c']}],
   'evidence':[], 'snapshots':[], 'autosaves':[], 'samples':[], 'skipped_waypoints':[], 'case_types':['enroute_efob'],'markers':[]}
  for i,(sid,utc,lat) in enumerate([('a','2026-11-07 17:15:00 UTC',50.00),('b','2026-11-07 17:10:00 UTC',50.10),('c','2026-11-07 17:17:00 UTC',50.20)]):
   image=Image.new('RGB',(1450,850),color=(35+i*45,75,105));image.save(folder/(sid+'.png'))
   state['evidence'].append({'id':sid,'original':sid+'.png','group_id':'g1','timestamp':utc,'purpose':'fms_fuel_load','phase':'Cruise','note':'FMS '+sid,
                            'context':{'lat':lat,'lon':9.6+i*.03,'altitude_ft':33000,'fob_kg':8500-i*80,'ff1_kg_h':3200+i*60,'ff2_kg_h':3190+i*70,'context_source':'simconnect'}})
  state['snapshots'].append({'id':'obs1','group_id':'g1','timestamp':'2026-11-07 17:11:00 UTC','issue_type':'enroute_efob','phase':'Cruise','fms_efob_kg':'8200','note':'FMS manual','context':{'lat':50.15,'lon':9.63,'context_source':'simconnect'}})
  state['groups'].append({'id':'g2','title':'Earlier phase','issue_type':'other','remark':'Earlier than group1','created_utc':'2026-11-07T16:55:00+00:00','screenshot_ids':[]})
  return state
 def test_chronological_order_and_individual_contexts(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=self.make_state(Path(tmp));e=event_list(s)
   self.assertEqual([x['label'] for x in e],['E01','E02']);self.assertEqual([x['raw_id'] for x in e],['g2','g1'])
   self.assertEqual([x['id'] for x in e[1]['screenshots']],['a','b','c'])
   self.assertEqual(e[1]['position']['lat'],50.1) # Earliest capture at 17:10
   self.assertEqual([x['context']['fob_kg'] for x in e[1]['screenshots']],[8500,8420,8340])
   s['groups'][0]['anchor_capture_id']='c'
   self.assertEqual(event_list(s)[1]['position']['lat'],50.2)
 def test_map_markers_remain_off_route_and_track_gaps(self):
  rows=[{'timestamp_unix':'1','latitude_deg':'50','longitude_deg':'8'},
        {'timestamp_unix':'6','latitude_deg':'50.01','longitude_deg':'8.02'},
        {'timestamp_unix':'50','latitude_deg':'52','longitude_deg':'10'},
        {'timestamp_unix':'55','latitude_deg':'52.01','longitude_deg':'10.02'}]
  self.assertEqual(len(track_from_rows(rows)),2)
  evt=[{'label':'E01','title':'Off-route','position':{'lat':52,'lon':13}}]
  g=geometry([{'lat':50,'lon':8},{'lat':50,'lon':9}],rows,evt)
  self.assertEqual(g['events'][0]['lon'],13)
  self.assertTrue(render_map([{'lat':50,'lon':8},{'lat':50,'lon':9}],rows,evt).startswith(b'\x89PNG'))
 def test_dateline_and_no_location(self):
  g=geometry([{'lat':10,'lon':179},{'lat':11,'lon':-179}],[],[])
  self.assertLess(g['bounds']['lon_max']-g['bounds']['lon_min'],3)
  self.assertTrue(render_map([],[],[]).startswith(b'\x89PNG'))
 def test_pdf_links_3_screens_and_no_bin(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);s=self.make_state(folder)
   telem=TelemetryStore(folder/'t.csv')
   for i in range(36):
    telem.append({'fob_kg':9100-i*7,'ff1_kg_h':3300,'ff2_kg_h':3400,'lat':50+i*.01,'lon':9.5,'altitude_ft':33000,'mach':.84,'total_weight_kg':195000,'vertical_speed_fpm':0}, 1794071000+i*5)
   def f(ev):
    p=folder/(ev['id']+'.png')
    return p if p.exists() else None
   raw=make_report(s,telem,f,graph_pil,telemetry_trend_png,evidence_audit,checklist,ISSUE_TYPES)
   pdf=fitz.open(stream=raw,filetype='pdf');txt='\n'.join(x.get_text() for x in pdf)
   self.assertGreaterEqual(len(pdf),3)
   self.assertIn('Route & Evidence Overview',txt)
   self.assertIn('Chronological Event Timeline',txt)
   self.assertIn('Before / after EFOB drop',txt)
   self.assertIn('Screenshot 3',txt)
   self.assertIn('FOB kg 8420',txt)
   self.assertNotIn('Certified engine',txt)
   self.assertTrue(pdf.get_toc(), 'PDF must provide event bookmarks')
   self.assertTrue(any(p.get_links() for p in pdf), 'PDF should provide links to events')

if __name__=='__main__':unittest.main()
