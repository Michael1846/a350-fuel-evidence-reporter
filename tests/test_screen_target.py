# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for automatic MSFS monitor capture; no Windows instance required."""
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import screen_target
import evidence_capture
import app
from telemetry_store import TelemetryStore


def window(title='Microsoft Flight Simulator 2024',exe='FlightSimulator2024.exe',
           box=(0,0,2560,1440),pid=4100,visible=True,minimized=False):
    return {'title':title,'process_name':exe,'window_bounds':box,'pid':pid,
            'hwnd':101,'visible':visible,'minimized':minimized}


class ScreenTargetTests(unittest.TestCase):
    def test_choose_simulator_not_other_windows(self):
        xs=[window('Chrome','chrome.exe',(0,0,3840,2160),pid=2),
            window(box=(-2560,0,0,1440)),window(title='Flight Simulator Wiki',exe='chrome.exe',pid=3)]
        self.assertEqual(screen_target.select_sim_window(xs)['pid'],4100)

    def test_choose_real_game_window_over_unknown_title(self):
        xs=[window(exe='',pid=20,box=(0,0,1920,1080)),window(pid=30,box=(0,0,1280,720))]
        self.assertEqual(screen_target.select_sim_window(xs)['pid'],30)

    def test_minimized_and_invisible_are_excluded(self):
        for x in [window(minimized=True),window(visible=False),window(box=(0,0,500,300))]:
            with self.assertRaises(screen_target.ScreenTargetError):
                screen_target.select_sim_window([x])

    def test_unknown_process_with_game_title_is_rejected(self):
        with self.assertRaises(screen_target.ScreenTargetError):
            screen_target.select_sim_window([window(exe='chrome.exe')])

    def test_ambiguous_simulators_fail_closed(self):
        a=window(pid=101)
        b=window(pid=102,box=(0,0,2550,1440))
        with self.assertRaisesRegex(screen_target.ScreenTargetError,'Multiple'):
            screen_target.select_sim_window([a,b])

    def test_monitor_api_result_including_negative_coordinates(self):
        m={'device':'\\\\.\\DISPLAY2','bounds':[-2560,0,0,1440],'primary':False}
        with patch.object(screen_target.os,'name','nt'),patch.object(screen_target,'_win32_windows',return_value=[window(box=(-2560,0,0,1440))]),patch.object(screen_target,'_monitor_for_window',return_value=m):
            result=screen_target.locate_msfs_monitor()
        self.assertEqual(result['bounds'],[-2560,0,0,1440])
        self.assertEqual(result['width'],2560)
        self.assertEqual(result['monitor'],'\\\\.\\DISPLAY2')

    def test_screenshot_auto_uses_msfs_bbox_not_foreground(self):
        target={'bounds':[-2560,-100,0,1340], 'monitor':'\\\\.\\DISPLAY2'}
        image=Image.new('RGB',(2560,1440),'white')
        with patch.object(evidence_capture,'os',SimpleNamespace(name='nt')),patch.object(evidence_capture,'locate_msfs_monitor',return_value=target),patch.object(evidence_capture.ImageGrab,'grab',return_value=image) as grab:
            binary,size,metadata=evidence_capture.grab_screen()
        grab.assert_called_once_with(bbox=(-2560,-100,0,1340),all_screens=True)
        self.assertEqual(size,(2560,1440))
        self.assertEqual(metadata['monitor'],'\\\\.\\DISPLAY2')
        self.assertTrue(binary.startswith(b'\x89PNG'))

    def test_no_simulator_never_falls_back_to_browser(self):
        with patch.object(evidence_capture,'os',SimpleNamespace(name='nt')),patch.object(evidence_capture,'locate_msfs_monitor',side_effect=screen_target.ScreenTargetError('No MSFS')) ,patch.object(evidence_capture.ImageGrab,'grab') as grab:
            with self.assertRaisesRegex(screen_target.ScreenTargetError,'No MSFS'):
                evidence_capture.grab_screen()
        grab.assert_not_called()

    def test_manual_monitor_selection_and_coordinates(self):
        monitor={'bounds':[-1600,100,0,1000],'device':'\\\\.\\DISPLAY2','primary':False}
        image=Image.new('RGB',(1600,900),'white')
        with patch.object(evidence_capture,'os',SimpleNamespace(name='nt')),patch.object(evidence_capture,'get_manual_monitor',return_value=monitor) as chosen,patch.object(evidence_capture.ImageGrab,'grab',return_value=image) as grabbed:
            raw,size,meta=evidence_capture.grab_screen('display:'+monitor['device'])
        chosen.assert_called_once_with(monitor['device'])
        grabbed.assert_called_once_with(bbox=(-1600,100,0,1000),all_screens=True)
        self.assertEqual(size,(1600,900))
        self.assertEqual(meta['method'],'manual monitor selection')

    def test_invalid_manual_monitor_fails_closed(self):
        with patch.object(evidence_capture,'os',SimpleNamespace(name='nt')),patch.object(evidence_capture,'get_manual_monitor',side_effect=screen_target.ScreenTargetError('Wrong display')),patch.object(evidence_capture.ImageGrab,'grab') as grab:
            with self.assertRaisesRegex(screen_target.ScreenTargetError,'Wrong display'):
                evidence_capture.grab_screen('display:fake')
        grab.assert_not_called()

    def test_endpoint_reports_detected_target(self):
        import threading,urllib.request
        from http.server import ThreadingHTTPServer
        with patch.object(app,'target_status',return_value={'detected':True,'monitor':'DISPLAY2','monitors':[]}):
            http=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(http.server_address[1])+'/api/screenshot-target',timeout=3) as response:
                    payload=json.load(response)
                self.assertTrue(payload['detected'])
                self.assertEqual(payload['monitor'],'DISPLAY2')
            finally:http.shutdown();http.server_close();worker.join(timeout=3)

    def test_capture_metadata_persisted_in_bundle_and_no_data_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'files').mkdir()
            (root/'case.json').write_text(json.dumps(app.DEF),encoding='utf-8')
            memory=io.BytesIO();Image.new('RGB',(100,50),'white').save(memory,'PNG')
            details={'monitor':'\\\\.\\DISPLAY2','bounds':[-2560,0,0,1440], 'method':'Win32 MonitorFromWindow'}
            status={'state':'connected','timestamp':time.time()-1,'flight_status':'GROUND','identity':{'title':'A350-900'},
                    'data':{'lat':49.0,'lon':10.0}}
            with patch.object(app,'DATA',root),patch.object(app,'FILES',root/'files'),patch.object(app,'STATE_PATH',root/'case.json'),\
                 patch.object(app,'CONFIG_PATH',root/'config.json'),\
                 patch.object(app,'TELEM_STORE',TelemetryStore(root/'data.csv')),patch.object(app.BRIDGE,'status',status),\
                 patch.object(app,'grab_screen',return_value=(memory.getvalue(),(100,50),details)):
                event,state=app.capture_evidence('msfs_monitor')
                self.assertEqual(event['context']['screen_capture']['monitor'],'\\\\.\\DISPLAY2')
                report=app.make_bundle(state)
                import zipfile
                with zipfile.ZipFile(io.BytesIO(report)) as z:
                    contexts=json.loads(z.read('screenshot_contexts.json'))
                    self.assertEqual(contexts[0]['context']['screen_capture']['bounds'],[-2560,0,0,1440])

if __name__=='__main__':unittest.main()
